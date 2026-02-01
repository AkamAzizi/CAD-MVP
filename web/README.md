# CAD-MVP Web

Web app for STEP upload, pipeline processing, and Assembly Q&A (Engineer Copilot).

## Quick Start

### 1. Backend (from project root)

```bash
pip install fastapi uvicorn python-multipart
uvicorn web.api:app --reload --port 8000
```

### 2. Frontend

```bash
cd web/frontend
npm install
npm run dev
```

### 3. Open

Go to **http://localhost:5173** in your browser.

- Upload a `.step` or `.stp` file (drag & drop or file picker)
- Click **Process** and wait for the pipeline + snapshot (and RAG index) to finish
- Use the chat to ask questions about the assembly (English or Swedish)

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/assemblies` | GET | List assemblies (from `cad_view_agents/output/*_snapshot.json`) |
| `/api/assemblies/upload` | POST | Multipart `file` (STEP); runs pipeline; returns `{ assembly_id, snapshot_path }` |
| `/api/assemblies/ask` | POST | Body `{ assembly_id, question }`; returns `{ answer, facts, sources }` |

The backend runs the pipeline via `cad_view_agents/run_pipeline.sh` and RAG via `python3 -m rag ask … --json` from `cad_view_agents/`.

## Structure

```
web/
├── api.py              # FastAPI app, CORS, endpoints
├── requirements.txt    # fastapi, uvicorn, python-multipart
├── uploads/            # Temporary STEP uploads (deleted on failure)
└── frontend/
    ├── src/
    │   ├── App.tsx     # Main layout, assembly selector
    │   ├── UploadCard.tsx
    │   ├── ChatPanel.tsx
    │   ├── main.tsx
    │   └── index.css
    ├── package.json
    └── vite.config.ts  # Proxy /api → localhost:8000
```

## Manual Test Checklist

- [ ] Backend: `uvicorn web.api:app --reload --port 8000` starts; `GET http://localhost:8000/api/assemblies` returns JSON
- [ ] Frontend: `npm run dev` in `web/frontend`; app loads at http://localhost:5173
- [ ] Upload: choose a STEP file, click Process; status shows "Processing…" then "Ready"; Assembly ID is shown
- [ ] Chat: click an example question or type one (e.g. "How many parts?"), Send; answer appears with optional Facts/Sources
- [ ] Error: upload a non-STEP file; expect 400 and clear message
- [ ] New file: after success, click "New file" and upload another STEP

## Dependencies

- **Backend:** Python 3.10+, `fastapi`, `uvicorn`, `python-multipart`
- **Pipeline/RAG:** Uses `cad_view_agents` (FreeCAD, Chroma, etc.)
- **Frontend:** Node 18+, `npm install` in `web/frontend`
