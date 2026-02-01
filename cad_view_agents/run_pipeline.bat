@echo off
REM Windows batch script wrapper for run_pipeline.py
REM Usage: run_pipeline.bat input.step [--out output.pdf] [other options]

python "%~dp0run_pipeline.py" %*
