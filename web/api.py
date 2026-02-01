"""
Minimal FastAPI backend for CAD-MVP: STEP upload + pipeline, Assembly Q&A (RAG).
Run: uvicorn web.api:app --reload --port 8000
(from project root)
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Paths (assume run from project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CAD_VIEW_AGENTS = PROJECT_ROOT / "cad_view_agents"
OUTPUT_DIR = CAD_VIEW_AGENTS / "output"
UPLOADS_DIR = PROJECT_ROOT / "web" / "uploads"
RUN_PIPELINE_PY = CAD_VIEW_AGENTS / "run_pipeline.py"
RUN_PIPELINE_SH = CAD_VIEW_AGENTS / "run_pipeline.sh"
RUN_RAG_SH = CAD_VIEW_AGENTS / "run_rag.sh"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".step", ".stp"}

app = FastAPI(title="CAD-MVP API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response models ---


class AskRequest(BaseModel):
    assembly_id: str
    question: str


# --- Helpers ---


def _check_step_extension(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def _parse_assembly_id_from_stdout(stdout: str) -> str | None:
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("ASSEMBLY_ID="):
            return line.split("=", 1)[1].strip()
    return None


def _list_assemblies() -> list[dict]:
    if not OUTPUT_DIR.is_dir():
        return []
    out = []
    for p in sorted(OUTPUT_DIR.glob("*_snapshot.json"), key=lambda x: x.name):
        try:
            with open(p, "r", encoding="utf-8") as f:
                snap = json.load(f)
            aid = snap.get("assembly_id", p.stem.replace("_snapshot", ""))
            # Läsbart namn från källfil (filnamn utan ändelse)
            src = snap.get("source_file", "") or ""
            label = (os.path.splitext(os.path.basename(src))[0] or aid).strip() or aid
            out.append({"assembly_id": aid, "label": label, "snapshot_path": str(p.relative_to(CAD_VIEW_AGENTS))})
        except Exception:
            aid = p.stem.replace("_snapshot", "")
            out.append({"assembly_id": aid, "label": aid, "snapshot_path": str(p.relative_to(CAD_VIEW_AGENTS))})
    return sorted(out, key=lambda x: (x.get("label") or x["assembly_id"]).lower())


# --- Endpoints ---


@app.get("/api/assemblies")
def list_assemblies():
    """List available assemblies (from output/*_snapshot.json)."""
    return {"assemblies": _list_assemblies()}


@app.post("/api/assemblies/upload")
async def upload_and_process(file: UploadFile = File(...)):
    """
    Upload a STEP file, run pipeline (snapshot + RAG index), return assembly_id.
    """
    import sys
    print("[API] POST /api/assemblies/upload received", file=sys.stderr, flush=True)
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename")
    if not _check_step_extension(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    safe_name = re.sub(r"[^\w.\-]", "_", file.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    save_path = UPLOADS_DIR / unique_name

    try:
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    abs_path = str(save_path.resolve())
    print(f"[API] File saved, running pipeline: {abs_path}", file=sys.stderr, flush=True)
    
    # Use cross-platform Python launcher if available, otherwise fall back to shell script
    if RUN_PIPELINE_PY.exists():
        # Use Python launcher (cross-platform)
        python_cmd = sys.executable
        pipeline_cmd = [python_cmd, str(RUN_PIPELINE_PY), abs_path]
    elif RUN_PIPELINE_SH.exists() and platform.system() != "Windows":
        # Fall back to shell script on Unix systems
        pipeline_cmd = ["bash", str(RUN_PIPELINE_SH), abs_path]
    else:
        raise HTTPException(
            status_code=500,
            detail="Pipeline launcher not found. Please ensure run_pipeline.py exists."
        )
    
    try:
        proc = subprocess.run(
            pipeline_cmd,
            cwd=str(CAD_VIEW_AGENTS),
            capture_output=True,
            text=True,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Pipeline timed out (10 min)")
    except Exception as e:
        save_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-2000:]
        save_path.unlink(missing_ok=True)
        if "Segmentation fault" in err or "segfault" in err.lower():
            raise HTTPException(
                status_code=500,
                detail=(
                    "FreeCAD crashed (segmentation fault) in headless mode. "
                    "You can run the pipeline manually: python cad_view_agents/run_pipeline.py <file.step> "
                    "Or choose an existing assembly below to use the Q&A chat."
                ),
            )
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {err}")

    assembly_id = _parse_assembly_id_from_stdout(proc.stdout or "")
    if not assembly_id:
        # Fallback: find latest snapshot by mtime
        snapshots = list(OUTPUT_DIR.glob("*_snapshot.json"))
        if not snapshots:
            save_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail="Pipeline ran but no snapshot found")
        latest = max(snapshots, key=lambda p: p.stat().st_mtime)
        try:
            with open(latest, "r", encoding="utf-8") as f:
                assembly_id = json.load(f).get("assembly_id", latest.stem.replace("_snapshot", ""))
        except Exception:
            assembly_id = latest.stem.replace("_snapshot", "")

    snapshot_path = f"output/{assembly_id}_snapshot.json"
    return {"assembly_id": assembly_id, "snapshot_path": snapshot_path}


@app.post("/api/assemblies/ask")
def ask(req: AskRequest):
    """
    Ask RAG a question about an assembly. Returns answer, facts, sources.
    """
    import sys
    print(f"[API] POST /api/assemblies/ask assembly_id={req.assembly_id!r} question={req.question[:50]!r}...", file=sys.stderr, flush=True)
    if not req.assembly_id.strip():
        raise HTTPException(status_code=400, detail="assembly_id required")
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question required")

    # Use subprocess so RAG runs in cad_view_agents context (output/, rag_chroma)
    # Use sys.executable to ensure we use the same Python interpreter
    python_cmd = sys.executable
    # Set UTF-8 encoding for Windows compatibility
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    try:
        proc = subprocess.run(
            [
                python_cmd, "-m", "rag", "ask",
                "--assembly-id", req.assembly_id,
                "--question", req.question,
                "--snapshots-dir", str(OUTPUT_DIR),
                "--json",
            ],
            cwd=str(CAD_VIEW_AGENTS),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',  # Replace problematic characters instead of failing
            env=env,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        print("[API] RAG request timed out after 120s", file=sys.stderr, flush=True)
        raise HTTPException(status_code=504, detail="RAG request timed out")
    except Exception as e:
        print(f"[API] RAG subprocess exception: {e}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=f"RAG failed: {e}")

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "")[-2000:]  # Show more error context
        print(f"[API] RAG failed with return code {proc.returncode}", file=sys.stderr, flush=True)
        print(f"[API] RAG stderr: {proc.stderr[:500] if proc.stderr else '(none)'}", file=sys.stderr, flush=True)
        print(f"[API] RAG stdout: {proc.stdout[:500] if proc.stdout else '(none)'}", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail=f"RAG error (exit {proc.returncode}): {err}")

    out = (proc.stdout or "").strip()
    if not out:
        print("[API] RAG returned empty output", file=sys.stderr, flush=True)
        raise HTTPException(status_code=500, detail="RAG returned empty output")
    
    # RAG or deps may print warnings before JSON; try full output first, then from first {
    data = None
    try:
        data = json.loads(out)
    except json.JSONDecodeError as e:
        start = out.find("{")
        if start >= 0:
            try:
                data = json.loads(out[start:])
            except json.JSONDecodeError:
                print(f"[API] RAG JSON parse error: {e}", file=sys.stderr, flush=True)
                print(f"[API] RAG output (first 500 chars): {out[:500]}", file=sys.stderr, flush=True)
                raise HTTPException(status_code=500, detail=f"RAG returned invalid JSON: {str(e)[:200]}")
        else:
            print(f"[API] RAG output contains no JSON: {out[:500]}", file=sys.stderr, flush=True)
            raise HTTPException(status_code=500, detail="RAG output contains no JSON")
    
    if data is None:
        raise HTTPException(status_code=500, detail="RAG returned invalid JSON")

    print("[API] RAG response ready", file=sys.stderr, flush=True)
    return {
        "answer": data.get("answer", ""),
        "facts": data.get("facts", []),
        "sources": data.get("sources", []),
    }


@app.get("/")
def root():
    return {"message": "CAD-MVP API", "docs": "/docs"}
