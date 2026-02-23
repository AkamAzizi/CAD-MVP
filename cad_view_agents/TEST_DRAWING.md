# Testing the 2D Drawing Generation

## Quick Start

### 1. Install Dependencies

First, make sure you have CADQuery installed:

```bash
cd cad_view_agents
pip install -r requirements.txt
```

This will install:
- `cadquery>=2.3.0` (CAD kernel for STEP import and projection)
- `ezdxf>=1.0.0` (for future DXF export)
- `reportlab>=4.0.0` (for PDF generation)

### 2. Test with a Simple STEP File

You can test using one of the existing STEP files in `web/uploads/`:

```bash
# From the cad_view_agents directory
python pipeline.py ../web/uploads/eb9f276cc74e4e4ba6fff36e05b3cc62_strut.step --out output/test_drawing.pdf --skip-techdraw=false
```

Or use the launcher (but note: it uses FreeCAD's Python, so CADQuery might not be available):

```bash
python run_pipeline.py ../web/uploads/eb9f276cc74e4e4ba6fff36e05b3cc62_strut.step --out output/test_drawing.pdf --skip-techdraw=false
```

### 3. What to Expect

The pipeline will:

1. **Import STEP file** using CADQuery
2. **Generate views** (front, top, isometric)
3. **Create layout** (sheet size, scale, view placement)
4. **Try CADQueryEngine first**:
   - If CADQuery is available: Uses new render engine
   - If not available: Falls back to TechDrawAgent
5. **Generate PDF** in `output/{assembly_id}/drawing/drawing.pdf`

### 4. Verify It's Working

Check the output:

```bash
# Check if PDF was created
ls -lh output/*/drawing/drawing.pdf

# Or on Windows:
dir output\*\drawing\drawing.pdf
```

The PDF should contain:
- At least one view with geometry (outer boundary outlines)
- Title block (bottom-right)
- BOM table (bottom-left, if parts available)
- Balloons (if parts are mapped correctly)

### 5. Check Logs

The pipeline will print status messages:

```
[6/8] Attempting CADQuery render engine...
  [OK] CADQuery engine available, using for rendering
  [OK] CADQuery engine generated PDF: output/.../drawing/drawing.pdf
```

If CADQuery is not available, you'll see:

```
[6/8] Attempting CADQuery render engine...
  [INFO] CADQuery engine not available, falling back to TechDraw
[6/8] Using TechDraw agent...
```

## Troubleshooting

### CADQuery Not Found

If you see "CADQuery engine not available":

```bash
pip install cadquery
```

### Import Errors

If you get import errors, make sure you're in the `cad_view_agents` directory:

```bash
cd cad_view_agents
python pipeline.py ...
```

### Empty PDF

If the PDF is created but empty:
- Check that the STEP file has valid geometry
- Check that `part_id_mapping` is correct (should be in snapshot)
- Look for errors in the pipeline output

### Projection Failures

If you see "Projection failed" errors:
- The STEP file might be too complex
- Try a simpler STEP file first
- Check that CADQuery can import the file: `python -c "import cadquery as cq; cq.importers.importStep('your_file.step')"`

## Testing with Python Directly (Recommended)

Since CADQuery doesn't require FreeCAD, you can run the pipeline directly with Python:

```bash
cd cad_view_agents
python -m pipeline ../web/uploads/eb9f276cc74e4e4ba6fff36e05b3cc62_strut.step --out output/test.pdf --skip-techdraw=false
```

This bypasses FreeCAD entirely and uses CADQuery directly.
