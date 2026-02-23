# FreeCAD TechDraw Worker Status

## Current Issues

The FreeCAD TechDraw worker is encountering several limitations when running in console mode (via `freecadcmd`):

1. **Template Required**: TechDraw pages require a template to export SVG/PDF, but templates can't be easily created or loaded in console mode.

2. **API Differences**: Some TechDraw APIs behave differently in console vs GUI mode:
   - `page.addObject()` doesn't exist - must use `doc.addObject()` then `page.addView()`
   - `page.getSVG()` doesn't exist - need template for export
   - `ProjectionType` property doesn't exist on views

3. **Export Limitations**: PDF export requires either:
   - GUI mode (TechDrawGui.exportPageAsPdf)
   - SVG export (requires template) + svglib conversion

## Workarounds

### Option 1: Use GUI Mode (Recommended for Testing)
Run FreeCAD with GUI instead of `freecadcmd`:
```powershell
# Use FreeCAD GUI instead of FreeCADCmd
& "C:\Program Files\FreeCAD 1.0\bin\FreeCAD.exe" -c "exec(open('render_workers/freecad_techdraw_worker.py').read())" ...
```

### Option 2: Use Existing TechDrawAgent
The existing `TechDrawAgent` in `agents/techdraw_agent.py` already handles console mode with a 3-tier fallback approach.

### Option 3: Create Template First
Create a TechDraw template file first, then load it in the worker.

## Next Steps

1. **Create a minimal TechDraw template** that can be bundled with the repo
2. **Update worker to load template** before creating page
3. **Test with GUI mode** to verify the worker logic works
4. **Fallback to TechDrawAgent** if worker continues to fail in console mode

## Testing

To test the worker manually:
```powershell
cd cad_view_agents
python run_pipeline.py ..\web\uploads\<step-file>.step
```

Check logs at: `output\asm_<id>\drawing\render.log`
