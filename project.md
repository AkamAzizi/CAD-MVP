# CAD-MVP: Automated Technical Drawing Generation System

## Project Overview

**CAD-MVP** is an automated system that converts 3D CAD assemblies (STEP files) into professional 2D technical drawings with balloons, bill of materials (BOM), and an intelligent Q&A system for engineering analysis. The system uses a multi-agent pipeline architecture to automate the entire process from STEP file import to PDF/DXF export, eliminating manual drawing creation.

## Key Features

### 1. Automated Technical Drawing Generation
- **Automatic View Selection**: Intelligently selects the best views (front, top, right, isometric) based on geometry analysis
- **2D Technical Drawings**: Converts 3D geometry to 2D drawings with proper hidden lines and scaling
- **Ballooning**: Automatic part numbering with balloons and leader lines
- **Bill of Materials (BOM)**: Generates complete parts list with unique item numbers, quantities, and metadata
- **Layout & Scaling**: Automatic layout on standard sheet sizes (A4, A3, A2, A1, A0) with optimal scaling
- **Export Formats**: PDF and DXF output formats

### 2. Engineering Report Generator
- **PDF and JSON Reports**: Generates comprehensive engineering reports from assembly snapshots
- **Rules-Based Insights**: Deterministic insights about fastener counts, complexity, repetition, and size extremes
- **Complexity Scoring**: Computes 0-100 complexity score based on part metrics
- **Health Check**: Overall assembly health score with warnings
- **BOM Analysis**: Complete bill of materials with volumes, bounding boxes, and materials
- **Manufacturing Hints**: Rules-based suggestions for manufacturing optimization

### 3. Engineer Copilot (RAG-based Q&A)
- **Natural Language Queries**: Ask questions about assemblies in natural language
- **Structured Answers**: Provides headline answers with supporting facts and sources
- **Intent Recognition**: Understands various question types (part counts, geometry analysis, BOM questions, etc.)
- **Vector Search**: Uses ChromaDB for semantic search over assembly snapshots

### 4. Web Interface
- **Upload & Process**: Drag-and-drop STEP file upload with processing pipeline
- **Report Generation**: Generate and download engineering reports with insights
- **Chat Interface**: Interactive Q&A interface with example questions
- **Assembly Management**: Browse and select from previously processed assemblies

## Architecture

### Multi-Agent Pipeline

The system uses specialized agents for different tasks:

1. **Import Agent**: Loads STEP files via FreeCAD and computes parts count and bounding box
2. **Assembly Analyzer**: Determines primary axis, aspect ratios, and assembly description
3. **View Generator & Scorer**: Creates candidate views and scores them for optimal selection
4. **Layout Engine**: Calculates sheet size, scale, and view placements
5. **TechDraw Agent**: Creates TechDraw pages, views, hidden lines, BOM tables, and balloons
6. **BOM Generator**: Extracts part metadata, assigns item numbers, and generates BOM tables
7. **Balloon Engine**: Places balloons per unique part and routes leader lines
8. **QA Agent**: Validates artifacts and ensures quality standards
9. **RAG Agent**: Handles question answering with intent routing and answer building

### Technology Stack

- **FreeCAD**: Open-source CAD software for 3D modeling and TechDraw
- **Python 3.10+**: Main programming language for pipeline and automation
- **FastAPI**: Web API framework for backend services
- **React + TypeScript**: Frontend web application
- **ChromaDB**: Vector database for RAG system
- **Sentence Transformers**: Embeddings for semantic search

## Project Structure

```
CAD-MVP/
├── cad_view_agents/          # Main pipeline and RAG system
│   ├── agents/               # Specialized agents (import, analyzer, techdraw, QA, RAG)
│   ├── core/                 # Core components (part tree, layout, BOM, balloon engine)
│   ├── rag/                  # RAG system (intent router, answer builder, vector store)
│   ├── pipeline.py           # Main pipeline orchestration
│   └── run_pipeline.sh       # Pipeline launcher script
├── web/                      # Web application
│   ├── api.py                # FastAPI backend
│   └── frontend/             # React frontend
├── docs/                     # Documentation
│   └── ARCHITECTURE.md       # Detailed architecture documentation
└── outputs/                  # Generated artifacts and snapshots
```

## Use Cases

- **Rapid Prototyping**: Quickly generate technical drawings from 3D models
- **Automation**: Eliminate repetitive drawing tasks
- **Standardization**: Ensure consistent drawing formats and layouts
- **Documentation**: Automatically document CAD models for production or maintenance
- **Quality Assurance**: Automatic validation of drawings and assemblies
- **Engineering Analysis**: Query assemblies about parts, geometry, and structure

## Workflow

1. **Upload**: User uploads a STEP file via web interface or CLI
2. **Processing**: Pipeline runs through all agents:
   - Import and analyze assembly
   - Generate and select views
   - Create layout and scale
   - Generate TechDraw views
   - Create BOM and balloons
   - Export to PDF/DXF
3. **Indexing**: Assembly snapshot is created and indexed in vector database
4. **Q&A**: User can ask questions about the assembly using natural language

## Output Artifacts

- **PDF/DXF Files**: Technical drawings with views, balloons, and BOM
- **Assembly Snapshot**: JSON file containing complete assembly metadata
- **Metadata Files**: JSON files with pipeline trace, view plans, and QA results
- **RAG Index**: Vector database index for semantic search

## Supported Question Types

The Engineer Copilot supports various question intents:

- **Part Counting**: "How many parts are in the assembly?"
- **Geometry Analysis**: "Which part is the largest?"
- **Repetitive Parts**: "Which parts repeat the most?"
- **View Selection**: "Which view is best for a 2D drawing?"
- **BOM Questions**: "Are there any missing materials?"
- **Structure Analysis**: "What are the sub-assemblies?"
- **Engineering Guidance**: "What are the next steps?"

## Requirements

- **FreeCAD**: Installed and accessible via command line
  - macOS: `/Applications/FreeCAD.app`
  - Windows: `C:\Program Files\FreeCAD\bin\FreeCADCmd.exe`
  - Linux: `/usr/bin/freecadcmd`
- **Python 3.10+**: For web API and RAG system
- **Node 18+**: For frontend development

## Getting Started

### Backend Setup
```bash
pip install -r web/requirements.txt
pip install -r cad_view_agents/requirements.txt
uvicorn web.api:app --reload --port 8000
```

### Frontend Setup
```bash
cd web/frontend
npm install
npm run dev
```

### CLI Usage
```bash
cd cad_view_agents
python run_pipeline.py input.step --out output.pdf
```

## Documentation

- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**: Complete system architecture
- **[cad_view_agents/README.md](cad_view_agents/README.md)**: Pipeline details and CLI usage
- **[web/README.md](web/README.md)**: Web application setup

## License

See repository for license information.

---

**CAD-MVP** - Automating technical drawing generation from 3D CAD models
