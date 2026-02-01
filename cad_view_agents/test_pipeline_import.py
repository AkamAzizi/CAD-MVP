#!/usr/bin/env python3
"""Test script to verify pipeline imports work."""
import sys
import os

print("Testing pipeline imports...", flush=True)

try:
    print("1. Importing agents...", flush=True)
    from agents import import_agent, assembly_analyzer_agent, ai_analyzer_agent, qa_agent
    print("   ✓ Agents imported", flush=True)
    
    print("2. Importing TechDraw agent...", flush=True)
    from agents.techdraw_agent import TechDrawAgent
    print("   ✓ TechDraw agent imported", flush=True)
    
    print("3. Importing core modules...", flush=True)
    from core.part_tree import PartTree
    from core.view_candidates import ViewCandidateGenerator
    from core.view_scoring import ViewScorer
    from core.layout_engine import LayoutEngine
    from core.balloon_engine import BalloonEngine
    from core.bom_generator import BOMGenerator
    print("   ✓ Core modules imported", flush=True)
    
    print("\n✓ All imports successful!", flush=True)
    sys.exit(0)
    
except Exception as e:
    print(f"\n✗ Import failed: {e}", file=sys.stderr, flush=True)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
