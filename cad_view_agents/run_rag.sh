#!/usr/bin/env bash
# Run RAG CLI from anywhere: ./run_rag.sh list | ./run_rag.sh ask --assembly-id X --question "..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python3 -m rag "$@"
