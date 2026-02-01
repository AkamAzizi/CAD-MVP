#!/usr/bin/env python3
"""
Launcher script for pipeline.py that can be executed by freecadcmd.
This script sets up the environment and calls pipeline.py's main() function.
"""
import sys
import os

# Get the directory containing this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE_PY = os.path.join(SCRIPT_DIR, "pipeline.py")

# Change to script directory
os.chdir(SCRIPT_DIR)

# Add script directory to path
sys.path.insert(0, SCRIPT_DIR)

# sys.argv should already be set by the shell script
# If not, we'll set it from command line arguments
if len(sys.argv) == 1:
    # Try to get arguments from environment or use defaults
    # For now, just ensure we have at least the script name
    if not sys.argv or sys.argv[0] != 'pipeline.py':
        sys.argv = ['pipeline.py']

# Import and run the pipeline
# Since pipeline.py uses if __name__ == "__main__", we need to execute it
# in a way that makes __name__ == "__main__" true
import importlib.util
spec = importlib.util.spec_from_file_location("__main__", PIPELINE_PY)
module = importlib.util.module_from_spec(spec)
# Set __name__ to __main__ so the if __name__ == "__main__" block executes
module.__name__ = "__main__"
spec.loader.exec_module(module)
