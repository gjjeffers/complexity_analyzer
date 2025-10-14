from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import analyze_file, format_text_report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Static complexity analysis for Python files")
    p.add_argument("file", help="Path to a Python source file")
    p.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    p.add_argument("--show-operands", action="store_true", help="Include operators/operands maps in JSON output")
    args = p.parse_args(argv)

    path = Path(args.file)
    try:
        result = analyze_file(path)
    except FileNotFoundError:
        print(f"File not found: {path}", file=sys.stderr)
        return 2

    if args.format == "json":
        out = dict(result)
        if not args.show_operands:
            # Drop large maps to keep output succinct unless requested
            hal = dict(out.get("halstead", {}))
            hal.pop("operators", None)
            hal.pop("operands", None)
            out["halstead"] = hal
        print(json.dumps(out, indent=2))
    else:
        print(format_text_report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

