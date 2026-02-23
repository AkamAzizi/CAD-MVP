# CAD-MVP Web

Web app for STEP upload, pipeline processing, Engineering Report generation, and Assembly Q&A (Engineer Copilot).

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
- **Generate an engineering report** with insights, BOM, complexity analysis, and health checks
- Download PDF or view JSON report
- Use the chat to ask questions about the assembly (English or Swedish)
- Delete assemblies you no longer need

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/assemblies` | GET | List assemblies (from `cad_view_agents/output/*_snapshot.json`) |
| `/api/assemblies/upload` | POST | Multipart `file` (STEP); runs pipeline; returns `{ assembly_id, snapshot_path }` |
| `/api/assemblies/report` | POST | Body `{ assembly_id, format: "pdf"\|"json" }`; returns PDF file or JSON report |
| `/api/assemblies/{assembly_id}/report` | GET | Get report metadata (paths, generated_at) if exists |
| `/api/assemblies/{assembly_id}` | DELETE | Delete assembly (snapshot, output directory, RAG index) |
| `/api/assemblies/ask` | POST | Body `{ assembly_id, question }`; returns `{ answer, facts, sources }` |

The backend runs the pipeline via `cad_view_agents/run_pipeline.py` (with `--skip-techdraw` for demo mode) and RAG via `python3 -m rag ask … --json` from `cad_view_agents/`.

## Structure

```
web/
├── api.py              # FastAPI app, CORS, endpoints
├── requirements.txt    # fastapi, uvicorn, python-multipart
├── uploads/            # Temporary STEP uploads (deleted on failure)
└── frontend/
    ├── src/
    │   ├── App.tsx     # Main layout, assembly selector, delete functionality
    │   ├── UploadCard.tsx
    │   ├── ReportPanel.tsx  # Report generation UI
    │   ├── ChatPanel.tsx
    │   ├── main.tsx
    │   └── index.css
    ├── package.json
    └── vite.config.ts  # Proxy /api → localhost:8000
```

## Features

### Engineering Report Generator

- **PDF Reports:** 2-4 page professional reports with tables, charts, and formatted text
- **JSON Reports:** Machine-readable report data for programmatic access
- **Deterministic Insights:** Rules-based analysis (no AI/LLM required)
- **Reference Geometry Exclusion:** Automatically filters out axes, planes, and other non-physical parts
- **Complexity Scoring:** Calculates assembly complexity based on part count, variety, fasteners, and tree depth
- **Manufacturing Hints:** Provides actionable suggestions for manufacturing and assembly

### Assembly Management

- **List Assemblies:** View all processed assemblies
- **Delete Assemblies:** Remove assemblies and all associated data (snapshot, reports, RAG index)
- **Select Existing:** Choose from previously processed assemblies

## Manual Test Checklist

- [ ] Backend: `uvicorn web.api:app --reload --port 8000` starts; `GET http://localhost:8000/api/assemblies` returns JSON
- [ ] Frontend: `npm run dev` in `web/frontend`; app loads at http://localhost:5173
- [ ] Upload: choose a STEP file, click Process; status shows "Processing…" then "Ready"; Assembly ID is shown
- [ ] Report: click "Generate Report", wait for PDF/JSON; download PDF or view JSON summary
- [ ] Chat: click an example question or type one (e.g. "How many parts?"), Send; answer appears with optional Facts/Sources
- [ ] Delete: click × button next to an assembly, confirm; assembly is removed from list
- [ ] Error: upload a non-STEP file; expect 400 and clear message
- [ ] New file: after success, click "New file" and upload another STEP

## Dependencies

- **Backend:** Python 3.10+, `fastapi`, `uvicorn`, `python-multipart`
- **Pipeline/RAG:** Uses `cad_view_agents` (FreeCAD, Chroma, etc.)
- **Report Generation:** `reportlab` for PDF generation (included in `cad_view_agents/requirements.txt`)
- **Frontend:** Node 18+, `npm install` in `web/frontend`
