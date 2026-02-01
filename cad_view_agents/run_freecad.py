#!/usr/bin/env python3
"""
Cross-platform launcher for run.py using FreeCAD's Python interpreter.
Detects FreeCAD installation on macOS, Windows, and Linux.
Usage: python run_freecad.py "/path/to/file.step"
"""
import sys
import os
import platform
import subprocess
import shutil
from pathlib import Path

def find_freecad_cmd():
    """Find freecadcmd executable on current platform."""
    system = platform.system()
    
    # Check if FREECAD_CMD environment variable is set
    env_cmd = os.environ.get('FREECAD_CMD')
    if env_cmd and os.path.isfile(env_cmd):
        return env_cmd
    
    # Platform-specific paths
    if system == "Darwin":  # macOS
        paths = [
            "/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd",
            "/Applications/FreeCAD.app/Contents/MacOS/freecadcmd",
        ]
    elif system == "Windows":
        # Common Windows installation paths
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        paths = [
            os.path.join(program_files, "FreeCAD", "bin", "FreeCADCmd.exe"),
            os.path.join(program_files_x86, "FreeCAD", "bin", "FreeCADCmd.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "FreeCAD", "bin", "FreeCADCmd.exe"),
            "C:\\Program Files\\FreeCAD\\bin\\FreeCADCmd.exe",
            "C:\\Program Files (x86)\\FreeCAD\\bin\\FreeCADCmd.exe",
        ]
        # Also check if freecadcmd is in PATH
        if shutil.which("FreeCADCmd.exe"):
            return "FreeCADCmd.exe"
        if shutil.which("freecadcmd"):
            return "freecadcmd"
    else:  # Linux
        paths = [
            "/usr/bin/freecadcmd",
            "/usr/local/bin/freecadcmd",
            os.path.expanduser("~/FreeCAD/bin/freecadcmd"),
            "/opt/freecad/bin/freecadcmd",
        ]
        # Check if freecadcmd is in PATH
        if shutil.which("freecadcmd"):
            return "freecadcmd"
    
    # Try all paths
    for path in paths:
        if os.path.isfile(path):
            return path
    
    # Last resort: try to find in PATH
    if system == "Windows":
        for cmd in ["FreeCADCmd.exe", "freecadcmd.exe", "freecadcmd"]:
            found = shutil.which(cmd)
            if found:
                return found
    else:
        found = shutil.which("freecadcmd")
        if found:
            return found
    
    return None

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <path_to_step_file>", file=sys.stderr)
        sys.exit(1)
    
    step_file = sys.argv[1]
    if not os.path.isfile(step_file):
        print(f"Error: STEP file not found: {step_file}", file=sys.stderr)
        sys.exit(1)
    
    script_dir = Path(__file__).parent.resolve()
    run_py = script_dir / "run.py"
    step_file_abs = os.path.abspath(step_file)
    
    if not run_py.exists():
        print(f"Error: run.py not found at {run_py}", file=sys.stderr)
        sys.exit(1)
    
    # Change to script directory
    os.chdir(script_dir)
    
    # Load environment variables from .env file if it exists
    env_file = script_dir / ".env"
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    
    # Find FreeCAD
    freecad_cmd = find_freecad_cmd()
    if not freecad_cmd:
        print("Error: FreeCAD not found. Please install FreeCAD or set FREECAD_CMD environment variable.", file=sys.stderr)
        print("\nCommon installation paths:", file=sys.stderr)
        system = platform.system()
        if system == "Darwin":
            print("  macOS: /Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd", file=sys.stderr)
        elif system == "Windows":
            print("  Windows: C:\\Program Files\\FreeCAD\\bin\\FreeCADCmd.exe", file=sys.stderr)
            print("  Or add FreeCAD to your PATH", file=sys.stderr)
        else:
            print("  Linux: /usr/bin/freecadcmd or install via package manager", file=sys.stderr)
        sys.exit(1)
    
    # Use freecadcmd (headless) to execute the script
    # The -c flag executes Python code directly
    python_code = f'''
import sys
import os
sys.argv = ['run.py', r'{step_file_abs}']
os.chdir(r'{script_dir}')
sys.path.insert(0, r'{script_dir}')
exec(open(r'{run_py}').read())
'''
    
    if platform.system() == "Windows":
        # On Windows, use -c flag with proper escaping
        cmd = [freecad_cmd, "-c", python_code]
    else:
        cmd = [freecad_cmd, "-c", python_code]
    
    result = subprocess.run(
        cmd,
        cwd=str(script_dir),
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
