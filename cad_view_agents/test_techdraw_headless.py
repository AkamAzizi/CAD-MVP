#!/usr/bin/env python3
"""
Test script to verify FreeCAD TechDraw works in headless mode.
"""
import sys

try:
    import FreeCAD
    print("OK: FreeCAD imported successfully")
except ImportError as e:
    print(f"FAIL: FreeCAD import failed: {e}")
    sys.exit(1)

try:
    import TechDraw
    print("OK: TechDraw module imported successfully")
except ImportError as e:
    print(f"FAIL: TechDraw import failed: {e}")
    print("  Note: TechDraw may not be available in headless mode")
    sys.exit(1)

# Try to create a simple TechDraw page
try:
    doc = FreeCAD.newDocument("TestDoc")
    page = doc.addObject("TechDraw::DrawPage", "Page")
    print("OK: TechDraw page created successfully")
    
    # Clean up
    FreeCAD.closeDocument("TestDoc")
    print("OK: TechDraw headless mode test PASSED")
    sys.exit(0)
except Exception as e:
    print(f"FAIL: TechDraw page creation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
