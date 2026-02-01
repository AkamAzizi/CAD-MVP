# CAD View Agents - Multi-agent CAD Snapshot Pack Pipeline

MVP pipeline for processing STEP files and generating standardized views and artifacts using FreeCAD.

> **Full architecture:** See [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for how all agents, pipeline, and RAG work together.

## Om Projektet

**CAD View Agents** är ett automationssystem som konverterar 3D CAD-modeller (STEP-filer) till professionella 2D-tekniska ritningar med automatisk generering av vyer, ballonger och materiallistor (BOM).

### Vad gör projektet?

Projektet automatiserar processen att skapa tekniska ritningar från 3D-modeller. Istället för att manuellt skapa ritningar i CAD-program, kan du enkelt mata in en STEP-fil och få ut en komplett PDF eller DXF-fil med:

1. **Automatiskt valda vyer** - Systemet analyserar 3D-modellen och väljer de bästa vyerna (fram, topp, höger, isometrisk, etc.)
2. **2D-tekniska ritningar** - Konverterar 3D-geometri till 2D-ritningar med dolda linjer och korrekt skalning
3. **Ballonger** - Automatisk numrering av delar med ballonger och ledarlinjer
4. **Materiallista (BOM)** - Genererar en komplett lista över alla delar i monteringen med unika artikelnummer
5. **Layout och skalning** - Automatisk layout på standardpappersstorlekar (A4, A3, A2, A1, A0) med optimal skalning

### Hur fungerar det?

Systemet använder en **multi-agent pipeline** där olika specialiserade "agenter" hanterar olika delar av processen:

- **Import Agent**: Läser in STEP-filen och analyserar geometrin
- **Assembly Analyzer**: Identifierar vad monteringen är och dess huvudsakliga orientering
- **View Generator**: Skapar kandidat-vyer från olika vinklar
- **View Scorer**: Poängsätter och väljer de bästa vyerna baserat på geometri
- **Layout Engine**: Beräknar optimal placering och skalning på ritningsbladet
- **TechDraw Agent**: Genererar 2D-ritningar med FreeCAD TechDraw
- **Balloon Engine**: Placerar ballonger och ledarlinjer för varje unik del
- **BOM Generator**: Skapar materiallista med artikelnummer och kvantiteter
- **PDF/DXF Exporter**: Exporterar till PDF eller DXF-format

### Användningsområden

- **Snabb prototypning** av tekniska ritningar från 3D-modeller
- **Automatisering** av repetitiva ritningsuppgifter
- **Standardisering** av ritningsformat och layout
- **Dokumentation** av CAD-modeller för produktion eller underhåll
- **Kvalitetssäkring** med automatisk validering av ritningar

### Teknisk stack

- **FreeCAD**: Open-source CAD-program för 3D-modellering och TechDraw
- **Python**: Huvudspråk för pipeline och automation
- **SVG/PDF/DXF**: Output-format för ritningar
- **Multi-agent arkitektur**: Modulär design med specialiserade komponenter

## Requirements

- macOS
- FreeCAD 1.0.2 installed at `/Applications/FreeCAD.app`
- No external Python dependencies (uses FreeCAD's bundled Python)

## How to Run the Pipeline

### Basic Usage (Original Pipeline)

```bash
cd cad_view_agents
./run_freecad.sh "/path/to/your/file.step"
```

### New Automated Pipeline (2D Drawing + Balloons + BOM)

The new `pipeline.py` generates complete technical drawings with balloons and BOM tables:

```bash
cd cad_view_agents
./run_pipeline.sh input.step --out output.pdf
```

**Options:**
- `--out, -o`: Output file path (PDF, DXF, or base name for both)
- `--sheet-size`: Sheet size (A4, A3, A2, A1, A0) - default: auto-select
- `--scale`: Manual scale factor - default: auto-calculate
- `--max-views`: Maximum number of views (default: 4)
- `--hidden-line-style`: Hidden line style (Dashed, DashDot, Solid) - default: Dashed
- `--use-ai`: Enable AI-enhanced view ranking (optional)

**Examples:**

```bash
# Basic usage - auto-generate PDF
./run_pipeline.sh input.step --out output.pdf

# Specify sheet size and scale
./run_pipeline.sh input.step --out output.pdf --sheet-size A3 --scale 0.5

# Generate both PDF and DXF
./run_pipeline.sh input.step --out output

# With AI-enhanced view selection
./run_pipeline.sh input.step --out output.pdf --use-ai
```

### Example (Original Pipeline)

```bash
./run_freecad.sh "/Users/akamazizi/Projects/Siemens NX automation/Pump Manifold v3.step"
```

### Expected Output

The pipeline will create an `output/` directory containing:

- **summary.json** - Parts count, bounding box, filename, run metadata, and QA results
- **trace.json** - Complete agent execution trace with timestamps
- **view_plan.json** - Standard view directions (front, top, right, iso)
- **Artifacts** (headless mode):
  - `model.stl` - Exported 3D model in STL format
- **Artifacts** (GUI mode, if available):
  - `front.png`, `top.png`, `right.png`, `iso.png` - Rendered views

### Output Structure

```
output/
├── summary.json
├── trace.json
├── view_plan.json
├── model.stl          # (headless mode)
└── *.png              # (GUI mode only)
```

### Pipeline Flow

1. **import_agent**: Imports STEP file, computes parts count and bounding box
2. **view_planner_agent**: Generates standard view directions
3. **renderer_agent**: 
   - If GUI available: Renders PNG images for each view
   - If headless: Exports STL model
4. **qa_agent**: Validates all artifacts exist and meet size thresholds
5. **orchestrator (run.py)**: Coordinates all agents and saves outputs

### Exit Codes

- `0` - Success
- `1` - Error or QA failure

### Notes

- The pipeline runs in **headless mode** by default using `freecadcmd`
- If FreeCAD GUI is available, PNG rendering will be attempted
- Headless mode always exports STL as a fallback
- All outputs are saved to `./output/` relative to the script directory

### Assembly Snapshot & RAG (Q&A)

After a pipeline run, an **Assembly Snapshot** (JSON + Markdown) is generated and saved (e.g. `output/asm_<name>_<hash>_snapshot.json`). If RAG deps are installed (`chromadb`, `sentence-transformers`), a vector index is built so you can ask questions:

1. **Run the pipeline first** (from `cad_view_agents`):
   ```bash
   ./run_pipeline.sh /path/to/file.step --out output/pump
   ```

2. **List available assemblies** (use one of the IDs shown):
   ```bash
   python3 -m rag list
   ```

3. **Ask a question** (use the assembly ID from `list`):
   ```bash
   python3 -m rag ask --assembly-id asm_pump_abc12345 --question "Hur många unika delar finns?"
   python3 -m rag ask --snapshot output/asm_pump_abc12345_snapshot.json --question "Vilka vyer valdes?" --json
   ```

**From project root (CAD-MVP):** RAG lives inside `cad_view_agents`, so either `cd cad_view_agents` first, or use the wrapper:
   ```bash
   ./cad_view_agents/run_rag.sh list
   ./cad_view_agents/run_rag.sh ask --assembly-id asm_strut_2cab1e9e --question "Hur många delar?"
   ```

Options: `--snapshots-dir` (default: `output`), `--rag-dir`, `--json`. See `docs/RAG_IMPLEMENTATION_PLAN.md` for full design.

## Web Frontend

A Vite + React web interface is available for upload, processing, and Assembly Q&A.

### Running the Web App

From project root:

```bash
# Backend
uvicorn web.api:app --reload --port 8000

# Frontend (separate terminal)
cd web/frontend
npm install
npm run dev
```

The frontend is available at `http://localhost:5173` and proxies `/api` to the backend.

### Features

- Upload STEP files (drag & drop or file picker)
- Run pipeline and get assembly snapshot + RAG index
- Chat-based Q&A with example questions (Engineer Copilot)
- All answers in English with headline, facts, sources

See `../docs/ARCHITECTURE.md` for full system architecture.
