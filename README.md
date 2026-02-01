# CAD-MVP

Automated technical drawing generation from STEP files + Engineer Copilot Q&A.

## Overview

CAD-MVP converts 3D CAD assemblies (STEP files) into 2D technical drawings with balloons and BOM, then lets you ask questions about the assembly in natural language.

- **Pipeline:** STEP → Import → Part Tree → View Selection → Layout → TechDraw → BOM & Balloons → PDF/DXF
- **RAG:** Assembly Snapshot + Intent Router → structured answers (headline, facts, sources)
- **Web UI:** Upload STEP, process, chat about the assembly

## Quick Start

### 1. Prerequisites

- **FreeCAD** installed (see platform-specific paths below)
  - **macOS**: `/Applications/FreeCAD.app`
  - **Windows**: `C:\Program Files\FreeCAD\bin\FreeCADCmd.exe` (or add to PATH)
  - **Linux**: `/usr/bin/freecadcmd` (or install via package manager)
- **Python 3.10+** (for web API and RAG)
- **Node 18+** (for frontend)

### 2. Backend

```bash
# Install backend deps
pip install -r web/requirements.txt
pip install -r cad_view_agents/requirements.txt

# Start API
uvicorn web.api:app --reload --port 8000
```

### 3. Frontend

```bash
cd web/frontend
npm install
npm run dev
```

### 4. Use

1. Open **http://localhost:5173**
2. Upload a `.step` or `.stp` file (or choose an existing assembly)
3. Click **Process** and wait for the pipeline to finish
4. Ask questions in the chat (e.g. "How many parts?", "Which part is largest?", "What are the next steps?")

## Project Structure

```
CAD-MVP/
├── cad_view_agents/     # Pipeline + RAG
│   ├── agents/          # Import, Assembly Analyzer, TechDraw, QA, RAG
│   ├── core/            # Part tree, layout, BOM, balloon engine, snapshot
│   ├── rag/             # Intent Router, Answer Builder, Chroma, embeddings
│   ├── pipeline.py      # Main pipeline
│   └── run_pipeline.sh  # FreeCAD launcher
├── web/
│   ├── api.py           # FastAPI backend
│   └── frontend/        # Vite + React
└── docs/
    └── ARCHITECTURE.md  # Full architecture docs
```

## Documentation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** – Architecture, agents, pipeline, RAG intents, API
- **[cad_view_agents/README.md](cad_view_agents/README.md)** – Pipeline details, CLI, RAG usage
- **[web/README.md](web/README.md)** – Web app setup and API

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/assemblies` | List assemblies |
| `POST /api/assemblies/upload` | Upload STEP, run pipeline, return `assembly_id` |
| `POST /api/assemblies/ask` | Ask RAG: `{ assembly_id, question }` → `{ answer, facts, sources }` |

## Example Questions (Engineer Copilot)

- How many parts are in the assembly?
- Which part is the largest?
- Which view is best for a 2D drawing?
- Which parts repeat the most?
- Are there any missing materials?
- What are the next steps?

## License

See repository.
