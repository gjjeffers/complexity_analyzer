from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from .languages import JavaAnalyzer, JavaScriptAnalyzer, PythonAnalyzer, TypeScriptAnalyzer
from .languages.base import BaseAnalyzer

__all__ = [
    "analyze_file",
    "format_text_report",
    "available_languages",
    "detect_language",
]


def _build_analyzers() -> List[BaseAnalyzer]:
    # Instantiate analyzers here. This allows lazy imports and future extensions.
    return [
        PythonAnalyzer(),
        JavaAnalyzer(),
        JavaScriptAnalyzer(),
        TypeScriptAnalyzer(),
    ]


_ANALYZERS: List[BaseAnalyzer] = _build_analyzers()
_LANGUAGE_MAP: Dict[str, BaseAnalyzer] = {a.language.lower(): a for a in _ANALYZERS}
_EXTENSION_MAP: Dict[str, BaseAnalyzer] = {}
for analyzer in _ANALYZERS:
    for ext in analyzer.extensions:
        _EXTENSION_MAP[ext.lower()] = analyzer


def available_languages() -> List[str]:
    return sorted(_LANGUAGE_MAP)


def detect_language(path: Path) -> Optional[str]:
    analyzer = _EXTENSION_MAP.get(path.suffix.lower())
    if not analyzer and path.name.lower().endswith(".d.ts"):
        analyzer = _EXTENSION_MAP.get(".d.ts")
    return analyzer.language if analyzer else None


def _get_analyzer(language: Optional[str], path: Path) -> BaseAnalyzer:
    if language:
        key = language.lower()
        analyzer = _LANGUAGE_MAP.get(key)
        if not analyzer:
            raise ValueError(f"No analyzer registered for language '{language}'. Available: {', '.join(available_languages())}")
        return analyzer

    detected = detect_language(path)
    if not detected:
        raise ValueError(f"Could not detect language from file extension '{path.suffix}'. Specify --language explicitly.")
    return _LANGUAGE_MAP[detected.lower()]


def analyze_file(file_path: str | Path, language: str | None = None) -> Dict:
    """
    Analyze a source file using the registered analyzer for the detected or specified language.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    analyzer = _get_analyzer(language, path)
    return analyzer.analyze(path)


def format_text_report(result: Dict) -> str:
    path = result.get("file_path", "<unknown>")
    lang = result.get("language", "<unknown>").capitalize()
    s = result.get("summary", {})
    c = result.get("cyclomatic", {})
    h = result.get("halstead", {})
    mi = result.get("maintainability_index", 0.0)

    lines = []
    lines.append(f"File: {path}")
    lines.append(f"Language: {lang}")
    lines.append("- Summary:")
    lines.append(
        f"  LOC={s.get('lines', 0)}  Code={s.get('code', 0)}  Comments={s.get('comments', 0)}  Blanks={s.get('blanks', 0)}"
    )
    docstrings = s.get("docstrings")
    if docstrings is not None:
        lines[-1] += f"  Docstrings={docstrings}"
    lines.append("- Cyclomatic Complexity:")
    lines.append(f"  Total={c.get('total', 0)}")
    fns = c.get("by_function") or []
    if fns:
        lines.append("  By Function (top 10):")
        for fn in fns[:10]:
            line = f"    {fn.get('name', '<unknown>')}"
            lineno = fn.get("lineno")
            end_lineno = fn.get("end_lineno")
            if lineno:
                line += f" (L{lineno}"
                if end_lineno:
                    line += f"-L{end_lineno}"
                line += ")"
            line += f": CC={fn.get('complexity', '?')}"
            lines.append(line)
    lines.append("- Halstead:")
    lines.append(
        f"  n1={h.get('n1_distinct_operators',0):.0f} n2={h.get('n2_distinct_operands',0):.0f} "
        f"N1={h.get('N1_total_operators',0):.0f} N2={h.get('N2_total_operands',0):.0f}"
    )
    lines.append(
        f"  vocab={h.get('vocabulary',0):.0f} length={h.get('length',0):.0f} "
        f"volume={h.get('volume',0.0):.2f} difficulty={h.get('difficulty',0.0):.2f}"
    )
    lines.append(
        f"  effort={h.get('effort',0.0):.2f} time_s={h.get('time_seconds',0.0):.2f} est_bugs={h.get('estimated_bugs',0.0):.4f}"
    )
    lines.append(f"- Maintainability Index: {mi:.2f}/100")
    warn = result.get("warnings") or []
    if warn:
        lines.append("- Warnings:")
        for w in warn:
            lines.append(f"  - {w}")
    return "\n".join(lines)
