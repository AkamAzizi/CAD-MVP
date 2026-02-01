"""
CLI for Assembly Q&A: ask --assembly-id <id> --question "..." or --snapshot <path> --question "..."
Run from cad_view_agents: python -m rag ask --assembly-id pump --question "..."
"""
import argparse
import json
import os
import sys

# Ensure cad_view_agents is on path when run as python -m rag
_rag_dir = os.path.dirname(os.path.abspath(__file__))
_cad_view_agents = os.path.dirname(_rag_dir)
if _cad_view_agents not in sys.path:
    sys.path.insert(0, _cad_view_agents)


def list_snapshots(snapshots_dir: str) -> None:
    """List available assembly snapshots in snapshots_dir."""
    if not os.path.isdir(snapshots_dir):
        print(f"No directory: {snapshots_dir}")
        print("Run the pipeline first to generate snapshots: ./run_pipeline.sh file.step --out output/name")
        return
    found = []
    for name in sorted(os.listdir(snapshots_dir)):
        if name.endswith("_snapshot.json"):
            path = os.path.join(snapshots_dir, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    snap = json.load(f)
                aid = snap.get("assembly_id", name.replace("_snapshot.json", ""))
                found.append((aid, path))
            except Exception:
                found.append((name.replace("_snapshot.json", ""), path))
    if not found:
        print(f"No snapshots in {snapshots_dir}.")
        print("Run the pipeline first: ./run_pipeline.sh file.step --out output/name")
        return
    print("Available assemblies (use --assembly-id or --snapshot):")
    for aid, path in found:
        print(f"  {aid}")
        print(f"    -> {path}")


def main():
    parser = argparse.ArgumentParser(description="Assembly Q&A: ask questions about a CAD assembly snapshot")
    sub = parser.add_subparsers(dest="command", help="Command")
    ask_parser = sub.add_parser("ask", help="Ask a question about an assembly")
    ask_parser.add_argument("--assembly-id", "-a", help="Assembly ID or alias (e.g. pump); run 'list' to see IDs")
    ask_parser.add_argument("--snapshot", "-s", help="Path to snapshot JSON (alternative to assembly-id)")
    ask_parser.add_argument("--question", "-q", required=True, help="Question in natural language")
    ask_parser.add_argument("--snapshots-dir", default="output", help="Directory with *_snapshot.json (default: output)")
    ask_parser.add_argument("--rag-dir", help="Chroma persist directory (default: snapshots-dir/rag_chroma)")
    ask_parser.add_argument("--json", action="store_true", help="Output raw JSON only")
    list_parser = sub.add_parser("list", help="List available assembly snapshots")
    list_parser.add_argument("--snapshots-dir", default="output", help="Directory to scan (default: output)")
    args = parser.parse_args()

    if args.command == "list":
        list_snapshots(getattr(args, "snapshots_dir", "output"))
        return
    if args.command != "ask":
        parser.print_help()
        sys.exit(0)

    from agents.rag_agent import ask as rag_ask

    if args.snapshot:
        if not os.path.isfile(args.snapshot):
            print(f"Error: Snapshot file not found: {args.snapshot}", file=sys.stderr)
            sys.exit(1)
        with open(args.snapshot, "r", encoding="utf-8") as f:
            snapshot = json.load(f)
        assembly_id = snapshot.get("assembly_id", "unknown")
        result = rag_ask(
            assembly_id,
            args.question,
            snapshot_loader=lambda _: snapshot,
            snapshots_dir=os.path.dirname(args.snapshot) or ".",
            rag_dir=args.rag_dir or os.path.join(os.path.dirname(args.snapshot), "rag_chroma"),
        )
    elif args.assembly_id:
        result = rag_ask(
            args.assembly_id,
            args.question,
            snapshots_dir=args.snapshots_dir,
            rag_dir=args.rag_dir,
        )
        if "Kunde inte hitta snapshot" in result.get("answer", ""):
            print(result["answer"], file=sys.stderr)
            print("Run: python -m rag list --snapshots-dir", args.snapshots_dir, "  # list available IDs", file=sys.stderr)
            print("Or run the pipeline first: ./run_pipeline.sh file.step --out output/name", file=sys.stderr)
            sys.exit(1)
    else:
        print("Error: provide either --assembly-id or --snapshot", file=sys.stderr)
        print("Run: python -m rag list  # to see available assembly IDs", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result.get("answer", ""))
        if result.get("facts"):
            print("\nFacts:")
            for f in result["facts"]:
                print(f"  - {f}")
        if result.get("sources"):
            print("\nSources:", result["sources"])


if __name__ == "__main__":
    main()
