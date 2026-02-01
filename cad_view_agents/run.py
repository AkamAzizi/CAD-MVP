#!/usr/bin/env python3
"""
CAD View Agents Pipeline Orchestrator
"""
import sys
import json
import time
import os

# Try to load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, continue without it

from agents import import_agent, assembly_analyzer_agent, view_planner_agent, renderer_agent, qa_agent, ai_analyzer_agent

print("RUN.PY STARTED")

# Validate arguments
if len(sys.argv) < 2:
    print("Usage: run.py <step_file_path>")
    sys.exit(1)

step_path = sys.argv[1]

# Validate STEP file exists
if not os.path.exists(step_path):
    print(f"Error: STEP file not found: {step_path}")
    sys.exit(1)

if not os.path.isfile(step_path):
    print(f"Error: Path is not a file: {step_path}")
    sys.exit(1)

trace = []

def log(agent, data):
    trace.append({
        "agent": agent,
        "data": data,
        "ts": time.time()
    })

try:
    # Ensure output directory exists
    os.makedirs("output", exist_ok=True)
    
    # Import
    print(f"Importing STEP file: {step_path}")
    imp = import_agent.run(step_path)
    log("import_agent", {"parts": imp["parts_count"], "bbox": imp["bbox"]})
    print(f"Imported {imp['parts_count']} parts")
    
    # Analyze assembly
    step_filename = os.path.basename(step_path)
    print("Analyzing assembly...")
    analysis = assembly_analyzer_agent.run(
        imp.get("doc"),
        imp["parts_count"],
        imp["bbox"],
        step_filename
    )
    log("assembly_analyzer_agent", analysis)
    print(f"Assembly: {analysis['description']}")
    
    # Plan views (AI-enhanced if available, uses assembly analysis)
    print("Planning views...")
    plan = view_planner_agent.run(analysis)
    log("view_planner_agent", plan)
    
    # Save view_plan.json
    with open("output/view_plan.json", "w") as f:
        json.dump(plan, f, indent=2)
    
    # Render
    print("Rendering...")
    try:
        render_result = renderer_agent.run(plan["views"], "output", imp.get("doc"))
        log("renderer_agent", render_result)
    except Exception as e:
        print(f"Rendering failed: {e}")
        render_result = {"mode": "headless", "artifacts": [], "error": str(e)}
        log("renderer_agent", render_result)
    
    # QA
    print("Running QA...")
    artifacts = render_result.get("artifacts", [])
    qa = qa_agent.run(artifacts)
    log("qa_agent", qa)
    
    # AI Analysis (optional - enabled via environment variable)
    print("Running AI analysis...")
    # Prepare summary data for AI analysis
    step_filename = os.path.basename(step_path)
    summary_data_for_ai = {
        "parts_count": imp["parts_count"],
        "bbox": imp["bbox"],
        "filename": step_filename
    }
    ai_analysis = ai_analyzer_agent.run(analysis, summary_data_for_ai, trace)
    log("ai_analyzer_agent", ai_analysis)
    if ai_analysis.get("enabled") and not ai_analysis.get("error"):
        print("AI analysis completed")
    elif ai_analysis.get("enabled"):
        print(f"AI analysis failed: {ai_analysis.get('error')}")
    else:
        print("AI analysis skipped (disabled)")
    
    # Prepare summary
    step_filename = os.path.basename(step_path)
    summary = {
        "parts_count": imp["parts_count"],
        "bbox": imp["bbox"],
        "filename": step_filename,
        "assembly_description": analysis.get("description", "Unknown"),
        "assembly_analysis": {
            "primary_axis": analysis.get("primary_axis"),
            "is_assembly": analysis.get("is_assembly", False),
            "reasoning": analysis.get("reasoning", [])
        },
        "run_metadata": {
            "timestamp": time.time(),
            "step_path": step_path
        },
        "qa": qa
    }
    
    # Add AI analysis if available
    if ai_analysis.get("enabled") and not ai_analysis.get("error"):
        summary["ai_analysis"] = {
            "provider": ai_analysis.get("provider"),
            "model": ai_analysis.get("model"),
            "analysis": ai_analysis.get("analysis"),
            "insights": ai_analysis.get("insights", {}),
            "recommendations": ai_analysis.get("recommendations", [])
        }
    elif ai_analysis.get("error"):
        summary["ai_analysis"] = {
            "error": ai_analysis.get("error")
        }
    
    # Save outputs
    with open("output/summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    with open("output/trace.json", "w") as f:
        json.dump(trace, f, indent=2)
    
    print("RUN.PY FINISHED")
    print(f"Output files created in: {os.path.abspath('output')}")
    
    # Don't fail if QA has warnings (like missing STL for complex models)
    if qa.get("status") == "fail" and artifacts:
        print(f"QA failed: {qa.get('issues', [])}")
        sys.exit(1)
    else:
        if qa.get("issues"):
            print(f"QA warnings: {qa.get('issues', [])}")
        sys.exit(0)
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    
    # Try to save trace even on error
    try:
        os.makedirs("output", exist_ok=True)
        with open("output/trace.json", "w") as f:
            json.dump(trace, f, indent=2)
    except:
        pass
    
    sys.exit(1)
