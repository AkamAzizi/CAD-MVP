# CAD-MVP Architecture

This document describes how all agents, the pipeline, RAG system, and web application work together.

---

## 1. Project Overview

**CAD-MVP** is an automated system that:

1. **Imports** STEP (.step / .stp) CAD files
2. **Processes** them through a multi-agent pipeline → 2D technical drawings, balloons, BOM
3. **Generates** an Assembly Snapshot (JSON + Markdown) for Q&A
4. **Indexes** snapshots for RAG (Retrieval-Augmented Generation)
5. **Provides** a web UI for upload + chat-based Q&A (Engineer Copilot)

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CAD-MVP System                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────┐  │
│  │  Web UI      │     │  cad_view_agents (Pipeline + RAG)                 │  │
│  │  (Vite+React)│◄───►│                                                   │  │
│  │  :5173       │     │  ┌─────────┐    ┌─────────────────────────────┐  │  │
│  └──────┬───────┘     │  │ web/api │───►│ Pipeline (run_pipeline.sh)   │  │  │
│         │             │  │ :8000   │    │  • Import Agent              │  │  │
│         │ proxy       │  └────┬────┘    │  • Assembly Analyzer         │  │  │
│         │ /api        │       │         │  • View Generator/Scorer     │  │  │
│         │             │       │         │  • Layout Engine             │  │  │
│         │             │       │         │  • TechDraw Agent            │  │  │
│         │             │       │         │  • Balloon Engine            │  │  │
│         │             │       │         │  • BOM Generator             │  │  │
│         │             │       │         │  • QA Agent                  │  │  │
│         │             │       │         └──────────────┬──────────────┘  │  │
│         │             │       │                        │                  │  │
│         │             │       │                        ▼                  │  │
│         │             │       │         ┌─────────────────────────────┐  │  │
│         │             │       │         │ Assembly Snapshot (JSON)    │  │  │
│         │             │       │         │ + RAG index (Chroma)        │  │  │
│         │             │       │         └──────────────┬──────────────┘  │  │
│         │             │       │                        │                  │  │
│         │             │       │         ┌──────────────▼──────────────┐  │  │
│         │             │       └────────►│ RAG (rag ask)             │  │  │
│         │             │                │  • Intent Router           │  │  │
│         │             │                │  • Answer Builder          │  │  │
│         │             │                │  • Vector Store (Chroma)   │  │  │
│         │             │                └────────────────────────────┘  │  │
│         │             │                                                   │  │
│         └─────────────┴───────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Pipeline Flow

The main pipeline (`cad_view_agents/pipeline.py`) runs in this order:

| Phase | Component | Description |
|-------|-----------|-------------|
| 1 | **Import Agent** | Loads STEP via FreeCAD, computes parts count and bounding box |
| 2 | **Part Tree** | Builds stable part IDs, geometry hashes, instances |
| 3 | **Assembly Analyzer** | Determines primary axis, aspect ratios, description |
| 4 | **View Generator + Scorer** | Creates candidate views, scores them (optional AI ranking) |
| 5 | **Layout Engine** | Sheet size, scale, view placements |
| 6 | **TechDraw Agent** | Creates TechDraw page, views, hidden lines, BOM table, balloons |
| 7 | **BOM Generator** | Extracts metadata, assigns item numbers, generates BOM table |
| 8 | **Balloon Engine** | Places balloons per unique part, routes leaders |
| 9 | **Snapshot + RAG** | Builds Assembly Snapshot JSON, chunks it, indexes in Chroma |
| 10 | **Export** | PDF/DXF export (optional; can fail in headless) |
| 11 | **QA Agent** | Validates artifacts exist and meet size thresholds |

---

## 4. Agents

### 4.1 Import Agent (`agents/import_agent.py`)

- **Input:** Path to STEP file
- **Output:** FreeCAD document, `parts_count`, `bbox` (x, y, z in mm)
- **Uses:** FreeCAD `Import.insert()` to load STEP

### 4.2 Assembly Analyzer Agent (`agents/assembly_analyzer_agent.py`)

- **Input:** FreeCAD doc, parts count, bbox, filename
- **Output:** `description`, `primary_axis` (x/y/z), `aspect_ratios`, `recommended_views`
- **Logic:** Deterministic geometry analysis; optional AI enhancement via `CAD_USE_AI_ANALYSIS=true`

### 4.3 View Planner Agent (`agents/view_planner_agent.py`)

- Used by `run.py` (original pipeline) for view directions
- Pipeline uses `ViewCandidateGenerator` + `ViewScorer` instead

### 4.4 AI Analyzer Agent (`agents/ai_analyzer_agent.py`)

- Optional: AI-enhanced assembly description, view ranking
- Controlled by `CAD_USE_AI_ANALYSIS` env var
- Uses OpenAI/Anthropic if configured

### 4.5 TechDraw Agent (`agents/techdraw_agent.py`)

- **Input:** Sheet size, view placements, part tree, balloons, BOM table
- **Output:** TechDraw page, views, balloons, BOM table; PDF/DXF export
- **Uses:** FreeCAD TechDraw module; fallback exporters if unavailable

### 4.6 Renderer Agent (`agents/renderer_agent.py`)

- Used by `run.py` for PNG rendering or STL export
- Not used by main pipeline

### 4.7 QA Agent (`agents/qa_agent.py`)

- **Input:** List of artifact paths
- **Output:** `{ status: "pass"|"fail", issues: [...] }`
- **Logic:** Checks files exist and meet minimum size (1 KB)

### 4.8 RAG Agent (`agents/rag_agent.py`)

- **Input:** `assembly_id`, `question`
- **Output:** `{ answer, facts, sources }`
- **Flow:** Load snapshot → optional vector retrieval → Intent Router → Answer Builder
- Called by web API and CLI (`python -m rag ask`)

---

## 5. RAG System (Engineer Copilot)

### 5.1 Components

| Component | Path | Role |
|-----------|------|------|
| **Chunking** | `rag/chunking.py` | Splits snapshot into text chunks for indexing |
| **Embeddings** | `rag/embeddings.py` | SentenceTransformers for vector search |
| **Vector Store** | `rag/vector_store.py` | Chroma DB for retrieval |
| **Intent Router** | `rag/intent_router.py` | Classifies question → intent + params |
| **Answer Builder** | `rag/answer_builder.py` | Builds structured answer (headline, facts, sources) |

### 5.2 Intent Router – Supported Intents

| Intent | Example Questions |
|--------|-------------------|
| `COUNT_PARTS` | "How many parts?", "Hur många delar?" |
| `LARGEST_PARTS` | "Which part is largest?", "Topp 5 största" |
| `REPETITIVE_PARTS` | "Which parts repeat the most?", "Vilka delar upprepas mest?" |
| `BEST_VIEWS` | "Which view is best for 2D?", "Varför front?" |
| `BOM_QUESTIONS` | "Are there missing materials?", "Saknar någon del material?" |
| `DETAIL_DRAWINGS` | "Which parts need detail drawings?" |
| `GEOMETRY_ANALYSIS` | "Extreme geometry?", "Aspect ratio?" |
| `WARNINGS_ERRORS` | "Any errors?", "Varför blev ritningen fel?" |
| `STRUCTURE_ANALYSIS` | "Parts along main axis?", "Sub-assemblies?" |
| `ENGINEER_COPILOT` | "What are the next steps?", "Missing views?" |
| `OVERVIEW` | "Describe this assembly" |
| `FALLBACK` | Unclear → generic answer + retrieval |

### 5.3 Answer Format

All answers have:

- **answer** (headline): One sentence answering the question
- **facts**: 3–8 measurable points (bullets)
- **sources**: Paths to snapshot fields (e.g. `parts_tree.parts`, `bom_preview[]`)

Answers are always in **English**, regardless of question language.

---

## 6. Assembly Snapshot Schema

Snapshot (`*_snapshot.json`) contains:

| Field | Description |
|-------|-------------|
| `assembly_id` | Stable ID (e.g. `asm_Pump_abc12345`) |
| `source_file` | STEP file path |
| `overview` | `parts_count_unique`, `parts_count_total`, `bbox_mm`, `primary_axis` |
| `parts_tree.parts` | Part IDs, names, `volume_mm3`, `bbox_mm`, `instances` |
| `bom_preview` | BOM rows: `item`, `part_number`, `description`, `quantity`, `material` |
| `pipeline_artifacts` | `selected_views`, metadata |
| `orientation_heuristics` | `view_recommendations` with scores |
| `validation_errors` | Any pipeline/QA issues |

Full schema: `cad_view_agents/docs/assembly_snapshot_schema.json`

---

## 7. Web Application

### 7.1 Backend (`web/api.py`)

- **FastAPI** app on port 8000
- **Endpoints:**
  - `GET /api/assemblies` – List assemblies (from `output/*_snapshot.json`)
  - `POST /api/assemblies/upload` – Upload STEP, run pipeline, return `assembly_id`
  - `POST /api/assemblies/ask` – RAG: `{ assembly_id, question }` → `{ answer, facts, sources }`
- **CORS:** Allows `localhost:5173` for frontend

### 7.2 Frontend (`web/frontend/`)

- **Vite + React + TypeScript**
- **Components:**
  - `App.tsx` – Main layout, assembly selector
  - `UploadCard.tsx` – Drag & drop STEP upload, Process button
  - `ChatPanel.tsx` – Q&A chat with example questions, facts/sources expandable
- **Proxy:** `/api` → `http://localhost:8000` (Vite config)
- **Port:** 5173

---

## 8. Run Scripts

| Script | Purpose |
|--------|---------|
| `cad_view_agents/run_pipeline.sh` | Run pipeline via FreeCAD (`freecadcmd`) |
| `cad_view_agents/run_rag.sh` | Run RAG CLI (`python3 -m rag list|ask`) |
| `cad_view_agents/run_freecad.sh` | Original pipeline (run.py) |
| `cad_view_agents/run.py` | Older orchestration (view_plan, render, QA) |

---

## 9. Dependencies

### Python (cad_view_agents)

- **Required:** FreeCAD (bundled Python for pipeline)
- **RAG:** `chromadb`, `sentence-transformers`, `openai`, `anthropic`, `python-dotenv`

### Python (web backend)

- `fastapi`, `uvicorn`, `python-multipart`

### Frontend

- Node 18+
- `react`, `react-dom`, `vite`, `@vitejs/plugin-react`, `typescript`

---

## 10. Data Flow Summary

```
STEP file → Upload API → run_pipeline.sh (FreeCAD)
    → Pipeline (import → part_tree → analysis → views → layout → techdraw → BOM → balloons)
    → Assembly Snapshot (JSON) + RAG index (Chroma)
    → Output: output/*_snapshot.json, output/*/rag_chroma/

User question → POST /api/assemblies/ask → python -m rag ask
    → Load snapshot → Intent Router → Answer Builder (or retrieval + fallback)
    → { answer, facts, sources } → ChatPanel
```
