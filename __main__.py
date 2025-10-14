from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import analyze_file, available_languages, format_text_report


def main(argv: list[str] | None = None) -> int:
    langs = available_languages()
    p = argparse.ArgumentParser(description="Static complexity analysis for supported languages")
    p.add_argument("file", help="Path to a source file")
    p.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    p.add_argument(
        "--language",
        choices=["auto", *langs],
        default="auto",
        help="Explicitly set the source language (defaults to auto-detect from extension)",
    )
    p.add_argument("--show-operands", action="store_true", help="Include operators/operands maps in JSON output")
    args = p.parse_args(argv)

    path = Path(args.file)
    try:
        selected_language = None if args.language == "auto" else args.language
        result = analyze_file(path, language=selected_language)
    except FileNotFoundError:
        print(f"File not found: {path}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 3

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
