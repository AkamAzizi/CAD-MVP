#!/bin/bash
# Robust CLI runner for CAD view agents pipeline using FreeCAD headless mode
# Usage: ./run_freecad.sh "/path/to/file.step"

STEP_FILE="$1"
if [ -z "$STEP_FILE" ]; then
    echo "Usage: $0 <path_to_step_file>"
    exit 1
fi

if [ ! -f "$STEP_FILE" ]; then
    echo "Error: STEP file not found: $STEP_FILE"
    exit 1
fi

# Get absolute paths
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_PY="$SCRIPT_DIR/run.py"
STEP_FILE_ABS="$(cd "$(dirname "$STEP_FILE")" && pwd)/$(basename "$STEP_FILE")"

# Change to script directory so output/ is created there
cd "$SCRIPT_DIR"

# Load environment variables from .env file if it exists
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(cat "$SCRIPT_DIR/.env" | grep -v '^#' | xargs)
fi

# Use freecadcmd (headless) to execute the script
# The -c flag executes Python code directly
/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd -c "
import sys
import os
sys.argv = ['run.py', '$STEP_FILE_ABS']
os.chdir('$SCRIPT_DIR')
sys.path.insert(0, '$SCRIPT_DIR')
exec(open('$RUN_PY').read())
"

EXIT_CODE=$?
exit $EXIT_CODE
