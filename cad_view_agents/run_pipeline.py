#!/usr/bin/env python3
"""
Cross-platform launcher for pipeline.py using FreeCAD's Python interpreter.
Detects FreeCAD installation on macOS, Windows, and Linux.
Usage: python run_pipeline.py input.step [--out output.pdf] [other options]
"""
import sys
import os
import platform
import subprocess
import json
import tempfile
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
            # Check versioned directories (e.g., "FreeCAD 1.0")
            os.path.join(program_files, "FreeCAD 1.0", "bin", "FreeCADCmd.exe"),
            os.path.join(program_files, "FreeCAD 0.21", "bin", "FreeCADCmd.exe"),
            os.path.join(program_files, "FreeCAD 0.20", "bin", "FreeCADCmd.exe"),
            # Standard paths
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
    script_dir = Path(__file__).parent.resolve()
    pipeline_py = script_dir / "pipeline.py"
    
    if not pipeline_py.exists():
        print(f"Error: pipeline.py not found at {pipeline_py}", file=sys.stderr)
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
            print("\nTo install FreeCAD on macOS:", file=sys.stderr)
            print("  brew install --cask freecad", file=sys.stderr)
            print("  Or download from: https://www.freecad.org/downloads.php", file=sys.stderr)
        elif system == "Windows":
            print("  Windows: C:\\Program Files\\FreeCAD\\bin\\FreeCADCmd.exe", file=sys.stderr)
            print("  Or add FreeCAD to your PATH", file=sys.stderr)
            print("\nTo install FreeCAD on Windows:", file=sys.stderr)
            print("  1. Download installer from: https://www.freecad.org/downloads.php", file=sys.stderr)
            print("  2. Install FreeCAD (default location: C:\\Program Files\\FreeCAD)", file=sys.stderr)
            print("  3. Or set environment variable: set FREECAD_CMD=C:\\path\\to\\FreeCADCmd.exe", file=sys.stderr)
            print("\nTo set FREECAD_CMD temporarily (this session only):", file=sys.stderr)
            print("  $env:FREECAD_CMD = 'C:\\Program Files\\FreeCAD\\bin\\FreeCADCmd.exe'", file=sys.stderr)
            print("\nTo set FREECAD_CMD permanently:", file=sys.stderr)
            print("  [System.Environment]::SetEnvironmentVariable('FREECAD_CMD', 'C:\\Program Files\\FreeCAD\\bin\\FreeCADCmd.exe', 'User')", file=sys.stderr)
        else:
            print("  Linux: /usr/bin/freecadcmd or install via package manager", file=sys.stderr)
            print("\nTo install FreeCAD on Linux:", file=sys.stderr)
            print("  Ubuntu/Debian: sudo apt-get install freecad", file=sys.stderr)
            print("  Fedora: sudo dnf install freecad", file=sys.stderr)
            print("  Or download from: https://www.freecad.org/downloads.php", file=sys.stderr)
        sys.exit(1)
    
    # Convert arguments to JSON format (handles Unicode properly)
    args = sys.argv[1:]
    args_json = json.dumps(args, ensure_ascii=False)
    
    # Create temporary files for arguments and script
    temp_dir = tempfile.gettempdir()
    temp_args_file = os.path.join(temp_dir, f"pipeline_args_{os.getpid()}.json")
    temp_script = os.path.join(temp_dir, f"pipeline_runner_{os.getpid()}.py")
    
    try:
        # Write arguments to file
        with open(temp_args_file, 'w', encoding='utf-8') as f:
            f.write(args_json)
        
        # Create the Python runner script
        runner_script = f'''# -*- coding: utf-8 -*-
import sys
import os
import json
import traceback

# Ensure user site-packages are available FIRST (before any other imports)
# This is critical for CADQuery, reportlab, etc. to be found
try:
    import site
    user_site = site.getusersitepackages()
    if user_site:
        if user_site not in sys.path:
            sys.path.insert(0, user_site)
        # Also ensure site-packages are initialized
        site.addsitedir(user_site)
except Exception:
    pass  # Ignore if site module not available or user site not enabled

# Get paths from environment
SCRIPT_DIR = r"{script_dir}"
ARGS_FILE = r"{temp_args_file}"
PIPELINE_PY = os.path.join(SCRIPT_DIR, 'pipeline.py')

# Change to script directory
os.chdir(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

# Ensure user site-packages are available (for CADQuery, reportlab, etc.)
# This is done silently - no debug output needed

try:
    # Read arguments from JSON file
    with open(ARGS_FILE, 'r', encoding='utf-8') as f:
        args = json.load(f)
    sys.argv = ['pipeline.py'] + args
    
    # Execute pipeline.py
    # Set __file__ in globals so the script knows its location
    import builtins
    globals()['__file__'] = PIPELINE_PY
    globals()['__name__'] = '__main__'
    
    with open(PIPELINE_PY, 'r', encoding='utf-8') as f:
        code = compile(f.read(), PIPELINE_PY, 'exec')
        exec(code, globals())
except Exception as e:
    print(f"ERROR: Pipeline failed with exception: {{e}}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''
        
        with open(temp_script, 'w', encoding='utf-8') as f:
            f.write(runner_script)
        
        # Set environment variables
        env = os.environ.copy()
        env['PIPELINE_SCRIPT_DIR'] = str(script_dir)
        env['PIPELINE_ARGS_FILE'] = temp_args_file
        
        # Use freecadcmd to execute the temporary script
        if platform.system() == "Windows":
            # On Windows, ensure we use the full path and proper escaping
            cmd = [freecad_cmd, temp_script]
        else:
            cmd = [freecad_cmd, temp_script]
        
        result = subprocess.run(
            cmd,
            cwd=str(script_dir),
            env=env,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        
        exit_code = result.returncode
        
        # Extract output path from arguments for SVG->PDF conversion
        output_path = None
        for i, arg in enumerate(args):
            if arg in ['--out', '-o'] and i + 1 < len(args):
                output_path = args[i + 1]
                break
            elif arg.startswith('--out='):
                output_path = arg[6:]
                break
            elif arg.startswith('-o='):
                output_path = arg[3:]
                break
        
        # If no explicit output path, determine default from first argument (input file)
        if not output_path and args:
            input_file = args[0]
            if os.path.isfile(input_file):
                base_name = os.path.splitext(os.path.basename(input_file))[0]
                output_path = os.path.join("output", base_name)
        
        # If output path doesn't end with .pdf, it's a base name (will have .pdf appended)
        if output_path:
            pdf_path = output_path if output_path.endswith('.pdf') else f"{output_path}.pdf"
            svg_path = pdf_path.replace('.pdf', '.svg')
            
            # Convert SVG to PDF if SVG exists and is not empty (Tier2 export)
            if os.path.isfile(svg_path) and os.path.getsize(svg_path) > 0:
                print("[Post-processing] Converting SVG to PDF...")
                try:
                    import cairosvg
                    cairosvg.svg2pdf(url=svg_path, write_to=pdf_path)
                    print(f"  [OK] Converted SVG -> PDF: {pdf_path}")
                    # Remove temporary SVG file
                    os.remove(svg_path)
                except ImportError:
                    print("  [INFO] cairosvg not available (install with: pip install cairosvg)")
                    print("  [INFO] Keeping placeholder PDF generated by Tier3 fallback")
                except Exception as e:
                    print(f"  [WARN] SVG->PDF conversion failed: {e}")
        
        return exit_code
    
    finally:
        # Clean up temporary files
        try:
            if os.path.exists(temp_script):
                os.remove(temp_script)
            if os.path.exists(temp_args_file):
                os.remove(temp_args_file)
        except Exception:
            pass

if __name__ == "__main__":
    sys.exit(main())
