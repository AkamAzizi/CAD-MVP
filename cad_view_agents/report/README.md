# Engineering Report Generator

The Engineering Report Generator creates comprehensive PDF and JSON reports from assembly snapshots, providing rules-based insights, complexity scoring, and health analysis.

## Features

- **Deterministic Insights**: All insights are rules-based, not LLM-generated (chat still uses RAG)
- **Complexity Scoring**: Computes 0-100 complexity score based on part count, uniqueness, fasteners, and tree depth
- **Health Check**: Overall assembly health score with warnings
- **BOM Analysis**: Complete bill of materials with volumes, bounding boxes, and materials
- **Repetition Analysis**: Identifies repeated parts and standardization opportunities
- **Manufacturing Hints**: Rules-based suggestions for manufacturing optimization

## Usage

### From Python

```python
from report.builder import ReportBuilder
from report.pdf import render_pdf

# Build report from snapshot
builder = ReportBuilder()
report = builder.build_from_snapshot("output/asm_pump_abc123_snapshot.json")

# Generate PDF
pdf_path = render_pdf(report, "output/asm_pump_abc123/report/report.pdf")

# Access report data
print(f"Complexity: {report.overview.complexity_score_0_100}/100")
print(f"Health: {report.health_check.score_0_100}/100")
print(f"Insights: {len(report.insights)}")
```

### From API

```bash
# Generate report PDF
curl -X POST http://localhost:8000/api/assemblies/report \
  -H "Content-Type: application/json" \
  -d '{"assembly_id": "asm_pump_abc123", "format": "pdf"}' \
  --output report.pdf

# Get report JSON
curl -X POST http://localhost:8000/api/assemblies/report \
  -H "Content-Type: application/json" \
  -d '{"assembly_id": "asm_pump_abc123", "format": "json"}'

# Get report metadata
curl http://localhost:8000/api/assemblies/asm_pump_abc123/report
```

## Report Structure

Reports are saved to `output/{assembly_id}/report/`:

- `report.json` - Full report JSON
- `report.pdf` - PDF report
- `report_meta.json` - Metadata (paths, generated_at)

## Report Schema

### Overview
- `total_parts`: Total number of parts
- `unique_parts`: Number of unique parts
- `repeated_parts`: Number of repeated parts
- `bbox_mm`: Bounding box dimensions (x, y, z)
- `complexity_score_0_100`: Complexity score 0-100

### BOM
List of BOM items with:
- `item_no`: Item number
- `part_name`: Part name
- `qty`: Quantity
- `material`: Material (if available)
- `volume_mm3`: Volume in mm³ (if available)
- `bbox_mm`: Bounding box (if available)
- `category`: Category (e.g., "fastener")

### Insights
Rules-based insights with:
- `severity`: "info", "warn", or "risk"
- `title`: Insight title
- `details`: Detailed description
- `evidence`: Supporting data

### Health Check
- `score_0_100`: Health score 0-100
- `warnings`: List of warnings

## Rules

The rules engine generates deterministic insights:

1. **High Fastener Count**: Warns if total fasteners > threshold (default: 20)
2. **Fastener Variety**: Warns if unique fastener types > threshold (default: 5)
3. **Complexity**: Risk if complexity score > 70, info if > 50
4. **Repetition Opportunity**: Suggests standardization for repeated parts
5. **Size Extremes**: Detects volume dominance or very small parts

## Complexity Score Formula

```
Base: log(total_parts + 1) * 20 (max 60)
Unique ratio: (unique_parts / total_parts) * 20 (max 20)
Fastener penalty: min(fastener_count / 10, 20) (max 20)
Tree depth: min(tree_depth or 0, 10) (max 10)
Normalize to 0-100
```

## Configuration

Edit `config.py` to adjust thresholds:

- `COMPLEXITY_HIGH_THRESHOLD`: High complexity threshold (default: 70)
- `FASTENER_COUNT_WARNING_THRESHOLD`: Fastener count warning (default: 20)
- `FASTENER_VARIETY_WARNING_THRESHOLD`: Fastener variety warning (default: 5)
- `REPETITION_MIN_QTY`: Minimum quantity for repetition insight (default: 3)
- `VOLUME_DOMINANCE_THRESHOLD`: Volume dominance ratio (default: 0.5)

## Testing

Run tests with pytest:

```bash
cd cad_view_agents
pytest report/tests/
```

## Dependencies

- `pydantic`: Data models
- `reportlab`: PDF generation (already in requirements.txt)
