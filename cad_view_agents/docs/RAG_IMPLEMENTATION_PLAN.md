# RAG Implementation Plan: Assembly Q&A Bot

**Projekt:** CAD View Agents / Multi-agent CAD Snapshot Pack Pipeline  
**Mål:** Efter STEP-import ska användaren kunna ställa frågor till en "Assembly Q&A bot" som svarar utifrån extraherad modell-/pipelindata.

---

## A) Repo Audit Summary

### Var STEP-import sker
- **`agents/import_agent.py`** – `run(step_path)`:
  - `FreeCAD.newDocument`, `Import.insert(step_path, doc.Name)`, `doc.recompute()`
  - Returnerar: `doc`, `parts_count`, `bbox` (x/y/z mm)
  - Bbox-validering (realistiska storlekar) och fallback från enskilda objekt

### Var assembly-analys görs
- **`agents/assembly_analyzer_agent.py`** – `run(doc, parts_count, bbox, filename)`:
  - Primary axis (x/y/z), aspect ratios, description, `recommended_views`, `reasoning`, `is_assembly`, `ai_enhanced`

### Vilka data vi redan har
| Data | Källa | Fil/Modul |
|------|--------|-----------|
| Parts count, global bbox | Import | `import_agent.run()` |
| Part tree, stable IDs, geometry hash | PartTree | `core/part_tree.py` – `PartTree.build_tree(doc)` |
| Per-part: name, id, geometry_hash, metadata (material, label) | PartNode | `part_tree.py` – ej bbox/volume i API, men FreeCAD-objekt finns |
| BOM: item, part_number, description, qty, material | BOMGenerator | `core/bom_generator.py` – `extract_part_metadata()`, `BOMTable.to_dict()` |
| View candidates (name, direction, type) | ViewCandidateGenerator | `core/view_candidates.py` |
| View scoring (visibility, info density, symmetry) | ViewScorer | `core/view_scoring.py` – `score_all()` → list of (ViewCandidate, score) |
| Layout: sheet size, scale, view placements | LayoutEngine | `core/layout_engine.py` – `select_sheet_size()`, `calculate_scale()`, `place_views()` |
| TechDraw: page, views, balloons, BOM table | TechDrawAgent | `agents/techdraw_agent.py` |
| Export paths (PDF/DXF) | pipeline.py | `artifacts` list efter export |
| QA result (pass/fail, issues) | qa_agent | `agents/qa_agent.run(artifacts)` |
| Trace (alla agent-steg med ts) | pipeline | `trace` list i `run_pipeline()` retur |
| Metadata JSON (step_file, output_files, part_count, views, sheet_size, scale, balloon_mappings, bom, qa, export_errors) | pipeline.py | Sparas som `{output_base}.json` |

### Föreslagna ändringsställen
- **Ny modul:** `core/assembly_snapshot.py` – bygga Assembly Snapshot från pipeline-state.
- **Pipeline:** `pipeline.py` – efter analys/layout/BOM/export: anropa snapshot-generator, spara snapshot (JSON + MD), ev. indexera för RAG.
- **Ny agent/tool:** `agents/rag_agent.py` eller `core/rag/` – retrieval + (optional) LLM; exponeras som tool till Head Agent.
- **CLI/API:** ny entrypoint eller flagga i `pipeline_launcher`/`run_pipeline.sh` för `ask --assembly-id <id>`; ev. enkel HTTP API under `web/` om frontend ska använda det.

---

## B) Assembly Snapshot Spec

### Syfte
- **Maskinläsbar:** JSON för programmatisk användning och RAG-metadata.
- **Människoläsbar:** Markdown/text för embeddings och läsbarhet.
- **Spårbar:** `snapshot_version`, `assembly_id`, `timestamp`, `source_file_hash`.

### JSON Schema (översikt)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "AssemblySnapshot",
  "type": "object",
  "required": ["snapshot_version", "assembly_id", "timestamp", "source_file", "source_file_hash", "overview", "parts_tree", "bom_preview", "pipeline_artifacts"],
  "properties": {
    "snapshot_version": { "type": "string", "pattern": "^1\\.0$" },
    "assembly_id": { "type": "string", "description": "Stable ID derived from source path/hash" },
    "timestamp": { "type": "string", "format": "date-time" },
    "source_file": { "type": "string", "description": "STEP file path" },
    "source_file_hash": { "type": "string", "description": "SHA-256 of file (first N bytes or full)" },
    "overview": {
      "type": "object",
      "properties": {
        "parts_count_total": { "type": "integer" },
        "parts_count_unique": { "type": "integer" },
        "bbox_mm": { "type": "object", "properties": { "x": { "type": "number" }, "y": { "type": "number" }, "z": { "type": "number" } } },
        "primary_axis": { "type": "string", "enum": ["x", "y", "z"] },
        "description": { "type": "string" },
        "is_assembly": { "type": "boolean" }
      }
    },
    "parts_tree": {
      "type": "object",
      "description": "Flat list of parts (subassemblies = future); each has instances count via BOM",
      "properties": {
        "parts": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "id": { "type": "string" },
              "name": { "type": "string" },
              "label": { "type": "string" },
              "geometry_hash": { "type": "string" },
              "bbox_mm": { "type": "object", "properties": { "x": { "type": "number" }, "y": { "type": "number" }, "z": { "type": "number" } } },
              "volume_mm3": { "type": "number" },
              "placement": { "type": "array", "items": { "type": "number" }, "maxItems": 16 },
              "instances": { "type": "integer" }
            }
          }
        }
      }
    },
    "bom_preview": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "item": { "type": "integer" },
          "part_number": { "type": "string" },
          "description": { "type": "string" },
          "quantity": { "type": "integer" },
          "material": { "type": "string" }
        }
      }
    },
    "orientation_heuristics": {
      "type": "object",
      "properties": {
        "primary_axis": { "type": "string" },
        "aspect_ratios": { "type": "object" },
        "recommended_views": { "type": "object" },
        "view_recommendations": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "view_name": { "type": "string" },
              "score": { "type": "number" },
              "reason": { "type": "string" }
            }
          }
        }
      }
    },
    "pipeline_artifacts": {
      "type": "object",
      "properties": {
        "pdf_path": { "type": "string" },
        "dxf_path": { "type": "string" },
        "metadata_json_path": { "type": "string" },
        "view_svg_paths": { "type": "array", "items": { "type": "string" } },
        "selected_views": { "type": "array", "items": { "type": "string" } },
        "sheet_size": { "type": "string" },
        "scale": { "type": "number" },
        "view_scores": { "type": "object" }
      }
    },
    "validation_errors": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Relevant pipeline/QA/export errors and warnings"
    }
  }
}
```

### Exempel (minimal, 1 del)

```json
{
  "snapshot_version": "1.0",
  "assembly_id": "asm_a1b2c3d4",
  "timestamp": "2025-01-29T12:00:00Z",
  "source_file": "/path/to/pump.step",
  "source_file_hash": "sha256:abc123...",
  "overview": {
    "parts_count_total": 1,
    "parts_count_unique": 1,
    "bbox_mm": { "x": 100.0, "y": 50.0, "z": 30.0 },
    "primary_axis": "x",
    "description": "Single part. Primary orientation along X-axis.",
    "is_assembly": false
  },
  "parts_tree": {
    "parts": [
      {
        "id": "PART_75647",
        "name": "093043W",
        "label": "093043W",
        "geometry_hash": "a1b2c3...",
        "bbox_mm": { "x": 100.0, "y": 50.0, "z": 30.0 },
        "volume_mm3": 145000.5,
        "placement": [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1],
        "instances": 1
      }
    ]
  },
  "bom_preview": [
    { "item": 1, "part_number": "PART_75647", "description": "093043W", "quantity": 1, "material": "N/A" }
  ],
  "orientation_heuristics": {
    "primary_axis": "x",
    "aspect_ratios": { "xy": 2.0, "xz": 3.33, "yz": 1.67 },
    "view_recommendations": [
      { "view_name": "front", "score": 0.85, "reason": "Orthographic, high information density" },
      { "view_name": "top", "score": 0.82, "reason": "Orthographic" }
    ]
  },
  "pipeline_artifacts": {
    "pdf_path": "output/pump.pdf",
    "dxf_path": "output/pump.dxf",
    "metadata_json_path": "output/pump.json",
    "selected_views": ["front", "top", "iso", "right"],
    "sheet_size": "A2",
    "scale": 1.0,
    "view_scores": { "front": 0.85, "top": 0.82, "iso": 0.5, "right": 0.7 }
  },
  "validation_errors": []
}
```

### Markdown-representation (för embeddings)
En `to_markdown()` eller separat generator som producerar t.ex.:

```markdown
# Assembly Snapshot: asm_a1b2c3d4
Generated: 2025-01-29T12:00:00Z | Source: pump.step

## Overview
- Total parts: 1 | Unique parts: 1
- Bounding box (mm): X=100, Y=50, Z=30
- Primary axis: X. Single part.

## Parts
| Id | Name | Qty | Bbox (mm) | Volume (mm³) |
|----|------|-----|-----------|--------------|
| PART_75647 | 093043W | 1 | 100×50×30 | 145000.5 |

## BOM
| Item | Part Number | Description | Qty | Material |
|------|-------------|-------------|-----|----------|
| 1 | PART_75647 | 093043W | 1 | N/A |

## View recommendations
- front (0.85): Orthographic, high information density
- top (0.82): Orthographic

## Pipeline
- Sheet: A2, Scale: 1.0. Views: front, top, iso, right.
- Artifacts: output/pump.pdf, output/pump.dxf.

## Warnings / Errors
(none)
```

---

## C) Chunking & Retrieval Plan

### Chunktyper och metadata
- **overview** – En chunk: hela översikten (parts count, bbox, primary axis, description). Metadata: `chunk_type=overview`, `assembly_id`.
- **part** – En chunk per part: id, name, label, bbox, volume, instances. Metadata: `chunk_type=part`, `part_id`, `assembly_id`, `instances`.
- **bom** – En chunk för hela BOM-tabellen (eller en per rad om stor BOM). Metadata: `chunk_type=bom`, `assembly_id`.
- **view_recommendations** – En chunk: valda vyer + scores + kort motivering. Metadata: `chunk_type=view_recommendations`, `assembly_id`.
- **pipeline_artifacts** – En chunk: paths, sheet, scale. Metadata: `chunk_type=artifacts`, `assembly_id`.
- **validation_errors** – En chunk: alla fel/varningar. Metadata: `chunk_type=validation_errors`, `assembly_id`.

### Storlek och indelning
- Overview: 1 chunk, ~200–500 tecken.
- Parts: 1 chunk per part, ~100–300 tecken (inkl. bbox/volume).
- BOM: 1 chunk för MVP (hela tabellen); vid många rader kan delas i segment med `bom_offset`.
- View recommendations: 1 chunk.
- Artifacts: 1 chunk.
- Validation: 1 chunk (kan vara tom).

### Retrieval-routing (query → chunktyper)
- Frågor om "antal delar", "totalinstanser", "största del" → **overview** + **part** (sortering på volume/bbox).
- "Subassembly störst" → **overview** + **part** (MVP: ingen riktig subassembly-hierarki; kan besvaras med "en nivå" eller största part).
- "Bästa front/top view", "varför den vyn" → **view_recommendations** + **orientation_heuristics**.
- "Varför ritningen fel", "vad varnade pipeline" → **validation_errors** + **pipeline_artifacts**.
- Allmän översikt → **overview** först, sedan andra vid behov.

### Metadata för filter
- Varje chunk: `assembly_id` (obligatoriskt), `chunk_type`, `chunk_index` (om flera av samma typ).
- Part-chunks: `part_id`, `instances`, ev. `volume_mm3` för sortering.
- Index **per assembly_id** så retrieval alltid begränsas till en assembly.

---

## D) API / CLI Design

### CLI
- **Fråga efter pipeline-körning** (snapshot finns redan):
  ```bash
  python -m cad_view_agents.rag ask --assembly-id asm_a1b2c3d4 --question "Hur många unika delar finns?"
  ```
- **Assembly-id** kan vara:
  - Det som står i snapshot (t.ex. från `output/<base>_snapshot.json`),
  - eller ett kort alias: `--assembly-id pump` som mappar till senaste snapshot med `source_file` som slutar med `pump.step`.

- **Alternativ: fråga med path till snapshot**
  ```bash
  python -m cad_view_agents.rag ask --snapshot output/pump_snapshot.json --question "Vilka vyer valdes?"
  ```

### REST (om vi lägger till enkel server senare)
- `GET /assemblies` – lista assembly_ids (från sparade snapshots).
- `GET /assemblies/{assembly_id}/snapshot` – returnera snapshot JSON.
- `POST /assemblies/{assembly_id}/ask` – body: `{ "question": "..." }`, response: se nedan.

### Request/Response exempel
**Request**
```json
POST /assemblies/asm_a1b2c3d4/ask
{ "question": "Hur många unika parts och totalinstanser finns?" }
```

**Response**
```json
{
  "assembly_id": "asm_a1b2c3d4",
  "question": "Hur många unika parts och totalinstanser finns?",
  "answer": "Det finns 1 unik del och 1 totalinstans i monteringen.",
  "facts": [
    "Unique parts: 1",
    "Total instances: 1"
  ],
  "sources": [
    { "chunk_type": "overview", "field": "parts_count_unique, parts_count_total" }
  ]
}
```

### Output-format (kort och strukturerat)
- **answer:** 1–3 meningar.
- **facts:** punktlista med relevanta fakta.
- **sources:** vilka snapshot-chunks/fält som användes (för spårbarhet).

---

## E) Implementation Plan (PR-uppdelning)

### PR1: Assembly Snapshot generation
**Mål:** Generera och spara Assembly Snapshot (JSON + Markdown) efter pipeline-körning.

**Filer att skapa:**
- `cad_view_agents/core/assembly_snapshot.py`
  - `AssemblySnapshot` dataclass/typed dict enligt schema.
  - `build_snapshot(step_path, import_result, part_tree, analysis, bom_metadata, selected_views_with_scores, layout_engine, artifacts, trace, qa_result, export_errors)`.
  - Här plocka per-part bbox/volume från `part_tree` (PartNode.freecad_obj.Shape.BoundBox / Volume) om tillgängligt; annars utelämna eller sätt null.
  - `assembly_id` = deterministisk från `source_file` (t.ex. basename + hash av path eller fil-hash).
  - `source_file_hash` = SHA-256 av STEP-fil (första 64 KB eller hela om liten).
  - `save_snapshot(snapshot, output_dir)` → sparar `{assembly_id}_snapshot.json` och `{assembly_id}_snapshot.md`.
- `cad_view_agents/core/snapshot_schema.json` (valfritt) – JSON schema för validering.

**Filer att ändra:**
- `cad_view_agents/pipeline.py`:
  - Efter metadata sparas: anropa `build_snapshot(...)` med alla nödvändiga variabler (import_result, part_tree, analysis, selected_views + scores, layout_engine, artifacts, trace, qa_result, export_errors).
  - Spara snapshot till samma output-dir som metadata (t.ex. `output/`).
  - Lägg snapshot-filer i `result["artifacts"]` och ev. `result["metadata"]["snapshot_path"]`.

**Tester:**
- Unit: `build_snapshot` med mockade inputs ger giltig JSON som valideras mot schema (om vi har schema).
- Integration: kör pipeline på en liten STEP; kontrollera att `*_snapshot.json` och `*_snapshot.md` skapas och innehåller förväntade fält.

**Acceptance criteria:**
- Efter en lyckad pipeline-körning finns `{assembly_id}_snapshot.json` och `{assembly_id}_snapshot.md` i output-mappen.
- JSON innehåller overview, parts_tree (med bbox/volume där tillgängligt), bom_preview, orientation_heuristics, pipeline_artifacts, validation_errors.
- Markdown är läsbar och täcker samma information.

---

### PR2: Chunking + lokal vector store (retrieval only)
**Mål:** Chunking av snapshot till text + metadata, indexering per assembly_id, retrieval utan LLM.

**Filer att skapa:**
- `cad_view_agents/rag/__init__.py`
- `cad_view_agents/rag/chunking.py`
  - `chunk_snapshot(snapshot_dict) -> List[{ "text", "metadata" }]` enligt chunktyper ovan.
  - Text från snapshot (översättning av JSON-sektioner till korta meningar/rader för bättre retrieval).
- `cad_view_agents/rag/vector_store.py`
  - Abstrakt interface `VectorStore`: `add(assembly_id, chunks)`, `search(assembly_id, query, top_k) -> List[{ "text", "metadata", "score" }]`.
  - Implementation: **Chroma** (rekommenderat för enkelhet) eller FAISS; index namngivet med `assembly_id` (collection per assembly).
- `cad_view_agents/rag/embeddings.py`
  - Abstrakt interface `EmbeddingProvider`: `embed(texts: List[str]) -> List[List[float]]`.
  - Implementation: lokala sentence-transformers (t.ex. `all-MiniLM-L6-v2`) så att MVP inte kräver extern API; lätt att byta till OpenAI senare.

**Filer att ändra:**
- `cad_view_agents/requirements.txt`: lägg till `chromadb`, `sentence-transformers` (eller `faiss-cpu` om FAISS).
- `cad_view_agents/pipeline.py`: efter snapshot sparas, anropa chunking + `VectorStore.add(assembly_id, chunks)` och `EmbeddingProvider.embed()` för att fylla index (om RAG är aktiverat, t.ex. default True för MVP).

**Tester:**
- Unit: `chunk_snapshot` för given snapshot ger förväntat antal chunks och chunk_type i metadata.
- Unit: `VectorStore.add` + `search` returnerar relevant chunk för en enkel fråga (t.ex. "antal delar").

**Acceptance criteria:**
- Efter pipeline + snapshot skapas vector index för den assembly_id.
- `search(assembly_id, "Hur många delar?", top_k=3)` returnerar minst en chunk som innehåller parts count.

---

### PR3: RAG Agent (retrieval + structured answer without LLM)
**Mål:** "Assembly Q&A" som svarar med retrieval + regelbaserad sammanställning (inga externa API-anrop).

**Filer att skapa:**
- `cad_view_agents/rag/answer_builder.py`
  - `build_answer(question: str, retrieved_chunks: List, snapshot: dict) -> { "answer", "facts", "sources" }`.
  - Enkel heuristik: nyckelord i frågan ("antal", "delar", "unique", "instances") → plocka från overview/part chunks; "störst", "volym", "bbox" → sortera parts på volume/bbox; "vy", "front", "top", "bästa" → view_recommendations; "fel", "varning", "varför" → validation_errors.
  - Svaret: 1–3 meningar + facts + sources (chunk_type + field).
- `cad_view_agents/agents/rag_agent.py` (eller `cad_view_agents/rag/agent.py`)
  - `ask(assembly_id: str, question: str, vector_store, snapshot_loader) -> dict` med samma response-format som ovan.
  - Inuti: ladda snapshot (från disk), `vector_store.search(assembly_id, question, top_k=5)`, `answer_builder.build_answer(question, retrieved, snapshot)`.

**Filer att ändra:**
- `cad_view_agents/pipeline.py`: ingen obligatorisk ändring om RAG anropas via CLI.
- Ny CLI: `cad_view_agents/cli_rag.py` eller `cad_view_agents/rag/cli.py` med `ask --assembly-id ... --question ...` som anropar rag_agent och skriver ut JSON (eller formaterad text).

**Tester:**
- Unit: för given fråga + mockade chunks + snapshot, `build_answer` returnerar answer/facts/sources.
- Integration: `ask --assembly-id X --question "Hur många unika delar?"` returnerar svar som innehåller rätt antal.

**Acceptance criteria:**
- CLI `ask --assembly-id <id> --question "..."` returnerar strukturerat svar (answer, facts, sources).
- Frågorna "Hur många unika parts och totalinstanser?", "Vilka är topp 10 största delar?", "Föreslå bästa front/top view och varför", "Varför blev ritningen fel?" ger relevanta svar utifrån snapshot (regelbaserat).

---

### PR4: Embedding + LLM provider interfaces (plugga in OpenAI senare)
**Mål:** Abstrahera embeddings och LLM så att OpenAI (eller annan) kan pluggas in utan att ändra RAG-flödet.

**Filer att skapa/ändra:**
- `cad_view_agents/rag/providers/__init__.py`
- `cad_view_agents/rag/providers/embeddings.py`
  - `EmbeddingProvider` protocol/ABC; implementationer: `SentenceTransformerEmbeddings`, `OpenAIEmbeddings` (vid behov).
- `cad_view_agents/rag/providers/llm.py`
  - `LLMProvider` protocol: `generate(prompt, context) -> str`. Implementation: `NoOpLLM` (returnerar tom eller "use retrieval only"); senare `OpenAILLM`.
- `cad_view_agents/rag/answer_builder.py`: refaktorera så att om LLM finns konfigurerad anropas den med prompt + retrieved context; annars behåll nuvarande regelbaserade svar.

**Acceptance criteria:**
- RAG fungerar som idag med lokala embeddings och utan LLM.
- Konfiguration (env eller config) kan sätta `LLM_PROVIDER=openai` och `OPENAI_API_KEY`; då används OpenAI för att generera svar från retrieval (implementation kan vara PR5).

---

### PR5 (optional): OpenAI LLM integration
**Mål:** När API-nyckel finns, använda LLM för att generera 1–3 meningar + facts från retrieval.

- Implementera `OpenAILLM` i `rag/providers/llm.py`.
- Prompt: använd retrieved chunks som context, fråga som user; begär kort svar + punktlista + sources.
- Answer_builder anropar LLM om konfigurerad; annars regelbaserat.

---

## Definition of Done (MVP)

- [ ] STEP-fil körs genom pipeline; Assembly Snapshot (JSON + MD) genereras och sparas automatiskt.
- [ ] Snapshot innehåller: overview (parts total/unique, bbox, primary axis), parts med id/name/bbox/volume/instances där tillgängligt, BOM preview, view recommendations/scores, pipeline artifacts, validation/errors.
- [ ] Chunking och vector index per assembly_id fungerar; retrieval returnerar relevanta chunks för given fråga.
- [ ] CLI `ask --assembly-id <id> --question "..."` levererar svar med answer (1–3 meningar), facts, sources.
- [ ] Minst dessa frågetyper ger korrekta/kontrollerbara svar: antal unika/totalinstanser, topp N största delar (bbox/volym), bästa front/top view och varför, pipeline-fel/varningar.
- [ ] Inga externa API-krav i MVP; embeddings lokala (sentence-transformers); LLM valfri med tydlig provider-interface.
- [ ] RAG kan anropas som tool/agent av en Head Agent (t.ex. `rag_agent.ask(assembly_id, question)` returnerar strukturerat dict).

---

## Sammanfattning filer att skapa/ändra

| Åtgärd | Sökväg |
|--------|--------|
| Skapa | `core/assembly_snapshot.py` |
| Skapa | `core/snapshot_schema.json` (optional) |
| Skapa | `rag/__init__.py`, `rag/chunking.py`, `rag/vector_store.py`, `rag/embeddings.py`, `rag/answer_builder.py`, `rag/providers/embeddings.py`, `rag/providers/llm.py` |
| Skapa | `agents/rag_agent.py` (eller `rag/agent.py`) |
| Skapa | CLI: `rag/cli.py` eller `cli_rag.py` |
| Ändra | `pipeline.py` (snapshot-build + spara; ev. indexering) |
| Ändra | `requirements.txt` (chromadb, sentence-transformers) |

RAG-tjänsten är designad som en egen agent/tool som Head Agent kan anropa med `assembly_id` och `question`; retrieval är isolerad per assembly och arkitekturen är redo för att plugga in OpenAI (eller annan LLM) senare.

---

## RAG som tool i multi-agent-systemet

- **Head Agent** (eller orchestrator) kan anropa RAG som ett verktyg:
  - Input: `assembly_id` (eller path till snapshot), `question`.
  - Output: `{ "answer", "facts", "sources" }` – samma format som CLI/API.
- **Integration:** I en framtida orchestrator (t.ex. `run.py` eller en ny `orchestrator.py`) kan en "ask"-aktion delegeras till `rag_agent.ask(assembly_id, question)`.
- **Ingen beroende åt andra hållet:** Pipeline och övriga agenter behöver inte känna till RAG; snapshot genereras efter pipeline, och RAG läser bara sparad snapshot + index.
