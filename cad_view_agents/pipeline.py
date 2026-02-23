#!/usr/bin/env python3
"""
  Automation Pipeline: STEP -> 2D Drawing + Balloons + BOM -> PDF/DXF

Main CLI entry point for the automated technical drawing generation pipeline.
"""
import sys
import os
import json
import time
import argparse
import subprocess
from typing import Dict, List, Optional, Tuple

# Add current directory to path for imports
if '__file__' in globals():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
else:
    # When executed via exec(), use current working directory
    sys.path.insert(0, os.getcwd())

# Ensure user site-packages are available (for CADQuery, reportlab, etc.)
try:
    import site
    user_site = site.getusersitepackages()
    if user_site and user_site not in sys.path:
        sys.path.insert(0, user_site)
except Exception:
    pass  # Ignore if site module not available or user site not enabled

# Conditional FreeCAD imports - pipeline can start even if FreeCAD not available
try:
    from agents import import_agent, assembly_analyzer_agent, ai_analyzer_agent, qa_agent
    from agents.techdraw_agent import TechDrawAgent
    FREECAD_AVAILABLE = True
except ImportError as e:
    if "FreeCAD" in str(e):
        FREECAD_AVAILABLE = False
        import_agent = None
        assembly_analyzer_agent = None
        ai_analyzer_agent = None
        qa_agent = None
        TechDrawAgent = None
        print("Warning: FreeCAD not available. Pipeline requires FreeCAD for STEP import and analysis.")
        print("  Install FreeCAD or use run_pipeline.py which uses FreeCAD's Python interpreter.")
    else:
        raise

from core.part_tree import PartTree
from core.view_candidates import ViewCandidateGenerator
from core.view_scoring import ViewScorer
from core.layout_engine import LayoutEngine
from core.balloon_engine import BalloonEngine
from core.bom_generator import BOMGenerator
from core.assembly_snapshot import build_snapshot, save_snapshot
from core.drawing_plan import DrawingPlan
from pathlib import Path

# Lazy import of CADQueryEngine - only import when needed
CADQueryEngine = None


def log(trace: List[Dict], agent: str, data: Dict):
    """Log agent execution to trace."""
    trace.append({
        "agent": agent,
        "data": data,
        "ts": time.time()
    })


def select_top_views(scored_candidates: List[Tuple], max_views: int = 4) -> List[Tuple]:
    """
    Select top N views from scored candidates.
    
    Args:
        scored_candidates: List of (ViewCandidate, score) tuples
        max_views: Maximum number of views to select
        
    Returns:
        List of (ViewCandidate, score) tuples
    """
    # Always include front, top, and isometric if available
    selected = []
    required_names = ["front", "top", "iso"]
    
    # First, add required views
    for name in required_names:
        for candidate, score in scored_candidates:
            if candidate.name == name and candidate not in [v[0] for v in selected]:
                selected.append((candidate, score))
                break
    
    # Then add top-scoring views up to max_views
    for candidate, score in scored_candidates:
        if len(selected) >= max_views:
            break
        if candidate not in [v[0] for v in selected]:
            selected.append((candidate, score))
    
    # Ensure we have at least some views
    if not selected and scored_candidates:
        selected = scored_candidates[:max_views]
    
    return selected


def run_pipeline(step_path: str, output_path: str, options: Dict) -> Dict:
    """
    Main pipeline: STEP -> 2D Drawing + Balloons + BOM -> PDF/DXF
    
    Args:
        step_path: Path to input STEP file
        output_path: Path to output file (PDF, DXF, or base name)
        options: Pipeline options dictionary
        
    Returns:
        Result dictionary with status, artifacts, metadata, and trace
    """
    trace = []
    
    try:
        # Check if FreeCAD is available
        if not FREECAD_AVAILABLE:
            return {
                "status": "failed",
                "error": "FreeCAD is required for STEP import and analysis. Use run_pipeline.py or install FreeCAD.",
                "trace": trace
            }
        
        # Phase 1: Import & Assembly Analysis
        print(f"[1/8] Importing STEP file: {step_path}")
        import_result = import_agent.run(step_path)
        doc = import_result.get("doc")
        log(trace, "import_agent", {
            "parts_count": import_result["parts_count"],
            "bbox": import_result["bbox"]
        })
        print(f"  [OK] Imported {import_result['parts_count']} parts")
        
        if not doc:
            raise ValueError("Failed to import STEP file - no document created")
        
        # Build part tree with stable IDs
        print("[2/8] Building part tree...")
        part_tree = PartTree.build_tree(doc)
        log(trace, "part_tree", {
            "part_count": part_tree.get_part_count()
        })
        print(f"  [OK] Built part tree with {part_tree.get_part_count()} parts")
        
        # Analyze assembly
        step_filename = os.path.basename(step_path)
        print("[3/8] Analyzing assembly...")
        analysis = assembly_analyzer_agent.run(
            doc,
            import_result["parts_count"],
            import_result["bbox"],
            step_filename
        )
        log(trace, "assembly_analyzer_agent", analysis)
        print(f"  [OK] Assembly: {analysis.get('description', 'Unknown')}")
        
        # Phase 2: View Generation & Selection
        print("[4/8] Generating and selecting views...")
        candidate_generator = ViewCandidateGenerator()
        candidates = candidate_generator.generate_all_candidates(
            import_result["bbox"],
            analysis.get("primary_axis")
        )
        
        # Score candidates deterministically
        scorer = ViewScorer()
        scored_candidates = scorer.score_all(candidates, doc)
        
        # AI ranking (optional enhancement)
        if options.get("use_ai", False):
            try:
                # Use existing AI analyzer for view ranking
                ai_ranked = ai_analyzer_agent.run(analysis, {
                    "parts_count": import_result["parts_count"],
                    "bbox": import_result["bbox"],
                    "filename": step_filename
                }, trace)
                # For MVP, we'll use deterministic scores primarily
                # AI enhancement can be added in v2
            except Exception as e:
                print(f"  [WARN] AI ranking failed: {e}, using deterministic scores only")
        
        # Select top N views
        max_views = options.get("max_views", 4)
        selected_views = select_top_views(scored_candidates, max_views)
        log(trace, "view_selection", {
            "views": [v[0].name for v in selected_views],
            "scores": {v[0].name: v[1] for v in selected_views}
        })
        print(f"  [OK] Selected {len(selected_views)} views: {[v[0].name for v in selected_views]}")
        
        # Phase 3: Layout & Scale Calculation
        print("[5/8] Calculating layout and scale...")
        layout_engine = LayoutEngine()
        sheet_size = layout_engine.select_sheet_size(
            import_result["bbox"],
            len(selected_views),
            options.get("sheet_size")
        )
        scale = layout_engine.calculate_scale(
            [v[0] for v in selected_views],
            import_result["bbox"],
            options.get("scale")
        )
        
        # Create view placements
        view_placements = layout_engine.place_views(
            [v[0] for v in selected_views],
            import_result["bbox"]
        )
        log(trace, "layout", {
            "sheet_size": sheet_size.name,
            "scale": scale,
            "view_count": len(view_placements)
        })
        print(f"  [OK] Sheet: {sheet_size.name}, Scale: {scale}")
        
        # Phase 5: BOM Generation (needed for snapshot and drawing)
        print("[7/8] Generating BOM...")
        bom_generator = BOMGenerator()
        balloon_engine = BalloonEngine()
        item_numbers = balloon_engine.assign_item_numbers(part_tree)
        part_metadata = bom_generator.extract_part_metadata(part_tree, item_numbers)
        bom_table = bom_generator.generate_table(part_metadata)
        
        # Compute balloon assignments (needed for drawing plan)
        balloons = balloon_engine.place_balloons(view_placements, part_tree, item_numbers, sheet_size, bom_metadata=part_metadata)
        
        # Generate assembly_id (same logic as in snapshot building)
        from core.assembly_snapshot import _assembly_id
        assembly_id = _assembly_id(step_path)
        
        # Create initial metadata for drawing plan
        initial_metadata = {
            "assembly_id": assembly_id,
            "filename": step_filename,
            "sheet_size": sheet_size.name,
            "scale": scale,
            "views": [v[0].name for v in selected_views]
        }
        
        # Create drawing plan
        drawing_plan = DrawingPlan(
            assembly_id=assembly_id,
            sheet_size=sheet_size.name,
            scale=scale,
            view_placements=view_placements,
            bom_table=bom_table,
            balloons=balloons,
            metadata=initial_metadata
        )
        
        # Save drawing plan for debugging/reproducibility and post-processing
        plan_dir = Path("output") / assembly_id / "drawing"
        plan_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plan_dir / "drawing_plan.json"
        
        # Save full plan data including view placements for post-processing
        plan_dict = drawing_plan.to_dict()
        # Add view placement details for reconstruction
        plan_dict["view_placements_data"] = [
            {
                "view_name": vp.view.name,
                "view_direction": vp.view.direction,
                "view_type": vp.view.type,
                "position": vp.position,
                "scale": vp.scale,
                "width_mm": vp.width_mm,
                "height_mm": vp.height_mm
            }
            for vp in view_placements
        ]
        plan_dict["bom_table"] = bom_table.to_dict() if bom_table else {}
        plan_dict["step_path"] = step_path
        
        with open(plan_path, "w") as f:
            json.dump(plan_dict, f, indent=2)
        print(f"  [OK] Saved drawing plan: {plan_path}")
        print(f"  [INFO] To render with CADQuery (if not available in FreeCAD Python), run:")
        print(f"        python render_postprocess.py {plan_path} {step_path} {assembly_id}")
        
        # Check if we should skip TechDraw/export (demo mode - only snapshot + RAG)
        skip_techdraw = options.get("skip_techdraw", False)  # Default to False (generate drawings)
        
        artifacts = []  # Initialize artifacts list
        export_errors = []  # Initialize export_errors list
        render_engine_used = None
        
        if not skip_techdraw:
            # Always use FreeCAD TechDraw worker (easy mode)
            print("[6/8] Using FreeCAD TechDraw worker...")
            
            # Prepare drawing plan JSON with all necessary data
            output_dir = Path("output") / assembly_id / "drawing"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Build complete drawing plan for worker
            plan_dict = drawing_plan.to_dict()
            plan_dict["step_path"] = step_path
            
            # Add view details
            plan_dict["views"] = []
            for i, (view_candidate, score) in enumerate(selected_views):
                if i < len(view_placements):
                    placement = view_placements[i]
                    plan_dict["views"].append({
                        "name": view_candidate.name,
                        "direction": list(view_candidate.direction),
                        "position": list(placement.position),
                        "scale": placement.scale,
                        "width_mm": placement.width_mm,
                        "height_mm": placement.height_mm
                    })
            
            # Add view placements
            plan_dict["view_placements"] = []
            for placement in view_placements:
                plan_dict["view_placements"].append({
                    "position": list(placement.position),
                    "scale": placement.scale,
                    "width_mm": placement.width_mm,
                    "height_mm": placement.height_mm
                })
            
            # Add BOM rows
            if bom_table:
                plan_dict["bom"] = {
                    "rows": []
                }
                for part in bom_table.parts:
                    plan_dict["bom"]["rows"].append({
                        "item_number": getattr(part, 'item_number', 0),
                        "part_id": getattr(part, 'part_id', ''),
                        "quantity": getattr(part, 'quantity', 1)
                    })
            
            # Add balloons
            if balloons:
                plan_dict["balloons"] = []
                for balloon in balloons:
                    plan_dict["balloons"].append({
                        "item_number": getattr(balloon, 'item_number', 0),
                        "part_id": getattr(balloon, 'part_id', ''),
                        "anchor_point": list(getattr(balloon, 'anchor_point', [0, 0])),
                        "view_name": getattr(balloon, 'view_name', '')
                    })
            
            # Save complete drawing plan
            plan_path = output_dir / "drawing_plan.json"
            with open(plan_path, "w") as f:
                json.dump(plan_dict, f, indent=2)
            print(f"  [OK] Saved drawing plan: {plan_path}")
            
            # Call worker as subprocess
            # Since we're running via run_pipeline.py which uses FreeCAD's Python,
            # we need to use FreeCADCmd with -c flag to execute Python code directly
            # This prevents FreeCAD from auto-opening files
            worker_script = Path(__file__).parent / "render_workers" / "freecad_techdraw_worker.py"
            
            # Create Python code to execute the worker
            worker_code = f'''
import sys
import os
sys.path.insert(0, r"{Path(__file__).parent}")
os.chdir(r"{Path(__file__).parent}")

# Execute worker script
with open(r"{worker_script}", 'r', encoding='utf-8') as f:
    code = compile(f.read(), r"{worker_script}", 'exec')
    sys.argv = ['freecad_techdraw_worker.py', r"{plan_path}", r"{step_path}", r"{output_dir}"]
    exec(code, {{'__name__': '__main__', '__file__': r"{worker_script}"}})
'''
            
            # Use FreeCADCmd with -c flag to execute code directly
            import platform
            import shutil
            if platform.system() == "Linux":
                # Find FreeCADCmd
                freecad_cmd = shutil.which("freecadcmd") or "freecadcmd"
                worker_cmd = ["xvfb-run", "-a", freecad_cmd, "-c", worker_code]
            else:
                # On Windows, find FreeCADCmd
                freecad_cmd = None
                program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
                for version in ["1.0", "0.21", "0.20"]:
                    test_path = os.path.join(program_files, f"FreeCAD {version}", "bin", "FreeCADCmd.exe")
                    if os.path.isfile(test_path):
                        freecad_cmd = test_path
                        break
                
                if not freecad_cmd:
                    # Try to find in PATH
                    freecad_cmd = shutil.which("FreeCADCmd.exe") or shutil.which("freecadcmd")
                
                if freecad_cmd:
                    worker_cmd = [freecad_cmd, "-c", worker_code]
                else:
                    # Fallback: use current Python (should be FreeCAD's Python)
                    worker_cmd = [sys.executable, "-c", worker_code]
            
            # Run worker with timeout and logging
            log_path = output_dir / "render.log"
            max_retries = 1
            timeout_seconds = 300  # 5 minutes
            
            for attempt in range(max_retries + 1):
                try:
                    print(f"  [INFO] Running worker (attempt {attempt + 1}/{max_retries + 1})...")
                    with open(log_path, "w") as log_file:
                        result = subprocess.run(
                            worker_cmd,
                            stdout=log_file,
                            stderr=subprocess.STDOUT,
                            timeout=timeout_seconds,
                            cwd=str(Path(__file__).parent)
                        )
                    
                    if result.returncode == 0:
                        pdf_path = output_dir / "drawing.pdf"
                        if pdf_path.exists():
                            artifacts.append(str(pdf_path))
                            print(f"  [OK] Worker generated PDF: {pdf_path}")
                            render_engine_used = "FreeCADTechDraw"
                            break
                        else:
                            print(f"  [WARN] Worker completed but PDF not found: {pdf_path}")
                            if attempt < max_retries:
                                print(f"  [INFO] Retrying...")
                                continue
                    else:
                        print(f"  [WARN] Worker failed with exit code {result.returncode}")
                        if attempt < max_retries:
                            print(f"  [INFO] Retrying...")
                            continue
                        else:
                            export_errors.append(f"Worker failed with exit code {result.returncode}. Check {log_path}")
                except subprocess.TimeoutExpired:
                    print(f"  [ERROR] Worker timed out after {timeout_seconds} seconds")
                    export_errors.append(f"Worker timed out after {timeout_seconds} seconds")
                    if attempt < max_retries:
                        print(f"  [INFO] Retrying...")
                        continue
                except Exception as e:
                    print(f"  [ERROR] Worker execution failed: {e}")
                    export_errors.append(f"Worker execution failed: {e}")
                    if attempt < max_retries:
                        print(f"  [INFO] Retrying...")
                        continue
        else:
            print("[6/8] Skipping drawing generation (demo mode)")
        
        log(trace, "bom", {
            "part_count": len(part_metadata),
            "table_size": bom_generator.calculate_table_size(bom_table)
        })
        print(f"  [OK] Generated BOM with {len(part_metadata)} parts")
        
        # Phase 6: Ballooning (needed for snapshot metadata)
        print("[8/8] Computing balloon assignments...")
        # Compute balloon assignments (but don't place them if skipping TechDraw)
        balloons = balloon_engine.place_balloons(
            view_placements,
            part_tree,
            item_numbers,
            sheet_size,
            bom_metadata=part_metadata
        )
        balloons = balloon_engine.route_leaders(balloons, view_placements)
        
        # Balloons are handled by the worker, no need to add them here
        
        # Verify balloon count matches BOM row count
        expected_balloons = len(part_metadata)
        placed_balloons = len(balloons)
        log(trace, "ballooning", {
            "balloon_count": placed_balloons,
            "expected_count": expected_balloons,
            "item_numbers": item_numbers
        })
        if placed_balloons == expected_balloons:
            print(f"  [OK] Computed {placed_balloons} balloon assignments (matches BOM rows)")
        else:
            print(f"  [WARN] Computed {placed_balloons} balloon assignments (expected {expected_balloons} from BOM rows)")
        
        # Save metadata + snapshot BEFORE export (so we have them even if export hangs)
        metadata_path = output_path + ".json" if not output_path.endswith((".pdf", ".dxf")) else output_path.rsplit(".", 1)[0] + ".json"
        output_dir = os.path.dirname(metadata_path) or "."
        # artifacts and export_errors are already initialized earlier
        qa_result = {"status": "skip", "issues": []}
        metadata = {
            "step_file": step_path,
            "output_files": artifacts,
            "part_count": part_tree.get_part_count(),
            "views": [v[0].name for v in selected_views],
            "sheet_size": sheet_size.name,
            "scale": scale,
            "balloon_mappings": {b.part_id: b.item_number for b in balloons},
            "bom": bom_table.to_dict(),
            "qa": qa_result,
            "export_errors": export_errors,
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        artifacts.append(metadata_path)
        print(f"  [OK] Saved metadata: {metadata_path}")
        try:
            snapshot = build_snapshot(
                step_path,
                import_result,
                part_tree,
                analysis,
                part_metadata,
                selected_views,
                layout_engine,
                artifacts,
                trace,
                qa_result,
                export_errors,
            )
            snapshot_paths = save_snapshot(snapshot, output_dir)
            artifacts.extend(snapshot_paths)
            metadata["snapshot_path"] = snapshot_paths[0] if snapshot_paths else None
            metadata["assembly_id"] = snapshot.get("assembly_id")
            print(f"  [OK] Saved assembly snapshot: {snapshot_paths[0]}")
        except Exception as snap_err:
            print(f"  [WARN] Assembly snapshot failed: {snap_err}")
            snapshot = None
        else:
            if options.get("rag", True):
                try:
                    from rag.chunking import chunk_snapshot
                    from rag.vector_store import ChromaVectorStore
                    from rag.embeddings import SentenceTransformerEmbeddings
                    chunks = chunk_snapshot(snapshot)
                    rag_dir = os.path.join(output_dir, "rag_chroma")
                    store = ChromaVectorStore(persist_directory=rag_dir)
                    emb = SentenceTransformerEmbeddings()
                    store.add(snapshot["assembly_id"], chunks, emb)
                    print(f"  [OK] RAG index updated for {snapshot.get('assembly_id', '')}")
                except Exception as rag_err:
                    print(f"  [WARN] RAG index skipped: {rag_err}")
        print("  [INFO] Snapshot + RAG ready.")
        
        # Phase 7: Export (skip if in demo mode or already exported by worker)
        if skip_techdraw:
            print("[Export] Skipping PDF/DXF export (demo mode - snapshot only)")
            if not export_errors:
                export_errors.append("Export skipped in demo mode")
        elif render_engine_used == "FreeCADTechDraw":
            # Already exported by FreeCAD TechDraw worker
            print("[Export] PDF already generated by FreeCAD TechDraw worker")
        else:
            # Worker failed or was skipped - no export available
            print("[Export] No PDF generated (worker failed or skipped)")
            if not export_errors:
                export_errors.append("Worker did not generate PDF")
        
        log(trace, "export", {"artifacts": artifacts, "errors": export_errors})
        
        # Phase 8: QA (only if we have artifacts and not in demo mode)
        if artifacts and not skip_techdraw:
            print("[QA] Running quality assurance...")
            qa_result = qa_agent.run(artifacts)
            log(trace, "qa_agent", qa_result)
            if qa_result.get("status") == "pass":
                print("  [OK] QA passed")
            else:
                print(f"  [WARN] QA issues: {qa_result.get('issues', [])}")
        else:
            print("[QA] Skipped (demo mode or no artifacts to validate)")
        
        # Update metadata with export result (artifacts, qa, export_errors)
        metadata["output_files"] = artifacts
        metadata["qa"] = qa_result
        metadata["export_errors"] = export_errors if export_errors else []
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)
        print(f"  [OK] Updated metadata: {metadata_path}")

        # Return success if we at least generated metadata, even if export failed
        return {
            "status": "warning" if export_errors else ("success" if qa_result.get("status") == "pass" else "warning"),
            "artifacts": artifacts,
            "metadata": metadata,
            "trace": trace
        }
        
    except Exception as e:
        error_msg = f"Pipeline error: {str(e)}"
        print(f"  [ERROR] {error_msg}")
        import traceback
        traceback.print_exc()
        
        log(trace, "error", {"message": error_msg, "exception": str(e)})
        
        return {
            "status": "failed",
            "error": error_msg,
            "trace": trace
        }


def main():
    """Main CLI entry point."""
    # Ensure output is flushed immediately
    import sys
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except:
        pass
    
    # Print startup message
    print("=" * 60, file=sys.stdout, flush=True)
    print("CAD Automation Pipeline", file=sys.stdout, flush=True)
    print("=" * 60, file=sys.stdout, flush=True)
    print("", file=sys.stdout, flush=True)
    
    parser = argparse.ArgumentParser(
        description="CAD Automation Pipeline: Generate 2D technical drawings from STEP files"
    )
    parser.add_argument(
        "input",
        help="Input STEP file path (.step or .stp)"
    )
    parser.add_argument(
        "--out", "-o",
        help="Output file path (PDF, DXF, or base name for both)",
        default=None
    )
    parser.add_argument(
        "--sheet-size",
        choices=["A4", "A3", "A2", "A1", "A0"],
        help="Sheet size (default: auto-select)",
        default=None
    )
    parser.add_argument(
        "--scale",
        type=float,
        help="Scale factor (default: auto-calculate)",
        default=None
    )
    parser.add_argument(
        "--max-views",
        type=int,
        help="Maximum number of views (default: 4)",
        default=4
    )
    parser.add_argument(
        "--hidden-line-style",
        choices=["Dashed", "DashDot", "Solid"],
        help="Hidden line style (default: Dashed)",
        default="Dashed"
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        help="Enable AI-enhanced view ranking (optional)"
    )
    parser.add_argument(
        "--skip-techdraw",
        action="store_true",
        default=False,
        help="Skip TechDraw/export generation (demo mode - snapshot only). Default: False (generate drawings)"
    )
    
    args = parser.parse_args()
    
    # Validate input file
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)
    
    if not args.input.lower().endswith((".step", ".stp")):
        print(f"Warning: Input file doesn't have .step or .stp extension: {args.input}")
    
    # Determine output path
    if args.out:
        output_path = args.out
    else:
        # Default: same name as input, in output directory
        base_name = os.path.splitext(os.path.basename(args.input))[0]
        os.makedirs("output", exist_ok=True)
        output_path = os.path.join("output", base_name)
    
    # Prepare options
    options = {
        "sheet_size": args.sheet_size,
        "scale": args.scale,
        "max_views": args.max_views,
        "hidden_line_style": args.hidden_line_style,
        "use_ai": args.use_ai,
        "skip_techdraw": args.skip_techdraw,  # Use command line argument (default: False)
        "rag": True,  # Enable RAG indexing
    }
    
    # Run pipeline
    result = run_pipeline(args.input, output_path, options)
    
    print()
    print("=" * 60)
    if result["status"] == "success":
        print("[SUCCESS] Pipeline completed successfully")
        print(f"Output files: {', '.join(result['artifacts'])}")
        aid = result.get("metadata", {}).get("assembly_id")
        if aid:
            print(f"ASSEMBLY_ID={aid}", flush=True)
        sys.exit(0)
    elif result["status"] == "warning":
        print("[WARNING] Pipeline completed with warnings")
        print(f"Output files: {', '.join(result['artifacts'])}")
        aid = result.get("metadata", {}).get("assembly_id")
        if aid:
            print(f"ASSEMBLY_ID={aid}", flush=True)
        sys.exit(0)
    else:
        print("[FAILED] Pipeline failed")
        print(f"Error: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        print("Pipeline starting...", flush=True)
        main()
    except Exception as e:
        print(f"FATAL ERROR in main(): {e}", file=sys.stderr, flush=True)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
