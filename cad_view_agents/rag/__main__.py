"""
Run as: python -m rag ask --assembly-id pump --question "Hur många delar?"
Must be run from cad_view_agents directory so that agents and rag packages are found.
"""
from .cli import main

if __name__ == "__main__":
    main()
