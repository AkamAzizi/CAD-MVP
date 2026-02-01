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
from typing import Dict, List, Optional, Tuple

# Add current directory to path for imports
if '__file__' in globals():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
else:
    # When executed via exec(), use current working directory
    sys.path.insert(0, os.getcwd())

from agents import import_agent, assembly_analyzer_agent, ai_analyzer_agent, qa_agent
from agents.techdraw_agent import TechDrawAgent
from core.part_tree import PartTree
from core.view_candidates import ViewCandidateGenerator
from core.view_scoring import ViewScorer
from core.layout_engine import LayoutEngine
from core.balloon_engine import BalloonEngine
from core.bom_generator import BOMGenerator
from core.assembly_snapshot import build_snapshot, save_snapshot


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
        
        # Phase 4: TechDraw Generation
        print("[6/8] Generating TechDraw views...")
        techdraw_agent = TechDrawAgent()
        page = techdraw_agent.create_page(sheet_size)
        
        if page is None:
            print("  [WARN] TechDraw not available, using fallback exporters")
        
        # Create TechDraw views
        techdraw_views = []
        for placement in view_placements:
            view = techdraw_agent.create_view(page, placement, doc)
            if view:
                techdraw_views.append(view)
        
        # Apply hidden lines
        techdraw_agent.apply_hidden_lines(techdraw_views, options.get("hidden_line_style", "Dashed"))
        print(f"  [OK] Created {len(techdraw_views)} TechDraw views")
        
        # Phase 5: BOM Generation (before balloons - needed for unique part count)
        print("[7/8] Generating BOM...")
        bom_generator = BOMGenerator()
        balloon_engine = BalloonEngine()
        item_numbers = balloon_engine.assign_item_numbers(part_tree)
        part_metadata = bom_generator.extract_part_metadata(part_tree, item_numbers)
        bom_table = bom_generator.generate_table(part_metadata)
        bom_position = bom_generator.place_table(sheet_size, bom_table)
        techdraw_agent.add_bom_table(page, bom_table, bom_position)
        log(trace, "bom", {
            "part_count": len(part_metadata),
            "table_size": bom_generator.calculate_table_size(bom_table)
        })
        print(f"  [OK] Generated BOM with {len(part_metadata)} parts")
        
        # Phase 6: Ballooning (using BOM metadata for unique parts only)
        print("[8/8] Placing balloons...")
        # Place balloons based on BOM rows (unique parts only)
        balloons = balloon_engine.place_balloons(
            view_placements,
            part_tree,
            item_numbers,
            sheet_size,
            bom_metadata=part_metadata  # Pass BOM metadata to place one balloon per unique part
        )
        balloons = balloon_engine.route_leaders(balloons, view_placements)
        techdraw_agent.add_balloons(page, balloons)
        
        # Verify balloon count matches BOM row count
        expected_balloons = len(part_metadata)
        placed_balloons = len(balloons)
        log(trace, "ballooning", {
            "balloon_count": placed_balloons,
            "expected_count": expected_balloons,
            "item_numbers": item_numbers
        })
        if placed_balloons == expected_balloons:
            print(f"  [OK] Placed {placed_balloons} balloons (matches BOM rows)")
        else:
            print(f"  [WARN] Placed {placed_balloons} balloons (expected {expected_balloons} from BOM rows)")
        
        # Save metadata + snapshot BEFORE export (so we have them even if export hangs)
        metadata_path = output_path + ".json" if not output_path.endswith((".pdf", ".dxf")) else output_path.rsplit(".", 1)[0] + ".json"
        output_dir = os.path.dirname(metadata_path) or "."
        artifacts = []
        export_errors = []
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
        print("  [INFO] Snapshot + RAG ready. Export may take a while (or hang in headless); you can Ctrl+C if needed.")
        
        # Phase 7: Export
        print("[Export] Exporting to PDF/DXF...")
        export_errors = []
        
        # Determine output format
        try:
            if output_path.endswith(".pdf"):
                try:
                    # Prepare metadata for export
                    export_metadata = {
                        "filename": os.path.basename(step_path),
                        "sheet_size": sheet_size.name,
                        "scale": scale,
                        "views": [v[0].name for v in selected_views]
                    }
                    pdf_path = techdraw_agent.export_pdf(page, output_path, 
                                                        view_placements, balloons, 
                                                        bom_table, export_metadata,
                                                        view_objects=techdraw_views)
                    if pdf_path:
                        artifacts.append(pdf_path)
                        print(f"  [OK] Exported PDF: {pdf_path}")
                except Exception as e:
                    export_errors.append(f"PDF export failed: {e}")
                    print(f"  [WARN] PDF export failed: {e}")
            elif output_path.endswith(".dxf"):
                try:
                    dxf_path = techdraw_agent.export_dxf(page, output_path)
                    if dxf_path:
                        artifacts.append(dxf_path)
                        print(f"  [OK] Exported DXF: {dxf_path}")
                except Exception as e:
                    export_errors.append(f"DXF export failed: {e}")
                    print(f"  [WARN] DXF export failed: {e}")
            else:
                # Export both
                try:
                    # Prepare metadata for export
                    export_metadata = {
                        "filename": os.path.basename(step_path),
                        "sheet_size": sheet_size.name,
                        "scale": scale,
                        "views": [v[0].name for v in selected_views]
                    }
                    pdf_path = techdraw_agent.export_pdf(page, output_path + ".pdf",
                                                        view_placements, balloons, bom_table, export_metadata,
                                                        view_objects=techdraw_views)
                    if pdf_path:
                        artifacts.append(pdf_path)
                        print(f"  [OK] Exported PDF: {pdf_path}")
                except Exception as e:
                    export_errors.append(f"PDF export failed: {e}")
                    print(f"  [WARN] PDF export failed: {e}")
                
                try:
                    dxf_path = techdraw_agent.export_dxf(page, output_path + ".dxf")
                    if dxf_path:
                        artifacts.append(dxf_path)
                        print(f"  [OK] Exported DXF: {dxf_path}")
                except Exception as e:
                    export_errors.append(f"DXF export failed: {e}")
                    print(f"  [WARN] DXF export failed: {e}")
        except Exception as e:
            export_errors.append(str(e))
            print(f"  [WARN] Export failed: {e}")
        
        log(trace, "export", {"artifacts": artifacts, "errors": export_errors})
        
        # Phase 8: QA (only if we have artifacts)
        if artifacts:
            print("[QA] Running quality assurance...")
            qa_result = qa_agent.run(artifacts)
            log(trace, "qa_agent", qa_result)
            if qa_result.get("status") == "pass":
                print("  [OK] QA passed")
            else:
                print(f"  [WARN] QA issues: {qa_result.get('issues', [])}")
        else:
            print("[QA] Skipped (no artifacts to validate)")
        
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
        "use_ai": args.use_ai
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
