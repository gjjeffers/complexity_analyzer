from __future__ import annotations

import ast
import keyword
import math
import tokenize
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class FunctionComplexity:
    name: str
    lineno: int
    end_lineno: Optional[int]
    complexity: int


def _read_bytes(path: Path) -> bytes:
    # Use binary read to preserve original newlines. tokenize handles encoding headers.
    return path.read_bytes()


def _iter_tokens(source_bytes: bytes) -> Iterable[tokenize.TokenInfo]:
    return tokenize.tokenize(BytesIO(source_bytes).readline)


def _is_docstring_node(node: ast.AST) -> bool:
    # Module, ClassDef, FunctionDef async/sync: first statement is a string literal => docstring
    body = getattr(node, "body", None)
    if not body:
        return False
    first = body[0]
    if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
        return isinstance(first.value.value, str)
    return False


def _count_loc(path: Path) -> Dict[str, int]:
    """
    Returns a dict with counts: lines, code, comments, blanks, docstrings
    """
    src = _read_bytes(path)

    total_lines = 0
    blank_lines = 0
    comment_lines = 0

    # Count via tokenization to reliably detect comments
    seen_comment_lines = set()
    for tok in _iter_tokens(src):
        if tok.type == tokenize.COMMENT:
            comment_lines += 1
            seen_comment_lines.add(tok.start[0])
        if tok.type == tokenize.NL or tok.type == tokenize.NEWLINE:
            total_lines = max(total_lines, tok.start[0])

    # Fallback if no NEWLINE tokens (e.g., empty file)
    if total_lines == 0:
        text = src.decode("utf-8", errors="ignore")
        total_lines = 0 if not text else text.count("\n") + 1

    # Count blanks by reading decoded text
    text = src.decode("utf-8", errors="ignore")
    lines = text.splitlines()
    blank_lines = sum(1 for line in lines if not line.strip())

    # Docstring lines: parse AST and count the triple-quoted strings used as docstrings
    docstring_lines = 0
    try:
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and _is_docstring_node(node):
                doc = ast.get_docstring(node, clean=False) or ""
                if doc:
                    # Estimate line count from node body[0]
                    expr = node.body[0]
                    start = getattr(expr, "lineno", None)
                    end = getattr(expr, "end_lineno", None)
                    if start is not None and end is not None:
                        docstring_lines += end - start + 1
    except SyntaxError:
        # If file is not valid Python, docstring detection fails gracefully
        pass

    # Source lines of code (SLOC): total - blank - comment-only - docstrings
    # Note: docstring lines may overlap with comment_lines=0 since docstrings are strings, not comments.
    sloc = max(0, total_lines - blank_lines - len(seen_comment_lines) - docstring_lines)

    return {
        "lines": total_lines,
        "code": sloc,
        "comments": len(seen_comment_lines),
        "blanks": blank_lines,
        "docstrings": docstring_lines,
    }


def _cyclomatic_for_function(fn: ast.AST) -> int:
    complexity = 1  # base complexity

    class Visitor(ast.NodeVisitor):
        def visit_If(self, node: ast.If) -> None:
            nonlocal complexity
            complexity += 1
            self.generic_visit(node)

        def visit_For(self, node: ast.For) -> None:
            nonlocal complexity
            complexity += 1
            self.generic_visit(node)

        def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
            nonlocal complexity
            complexity += 1
            self.generic_visit(node)

        def visit_While(self, node: ast.While) -> None:
            nonlocal complexity
            complexity += 1
            self.generic_visit(node)

        def visit_With(self, node: ast.With) -> None:
            # Treat context managers as decision points in some conventions (optional). Skip to stay conservative.
            self.generic_visit(node)

        def visit_Assert(self, node: ast.Assert) -> None:
            nonlocal complexity
            complexity += 1
            self.generic_visit(node)

        def visit_BoolOp(self, node: ast.BoolOp) -> None:
            nonlocal complexity
            # Each boolean operator adds (n-1)
            complexity += max(0, len(node.values) - 1)
            self.generic_visit(node)

        def visit_IfExp(self, node: ast.IfExp) -> None:
            nonlocal complexity
            complexity += 1
            self.generic_visit(node)

        def visit_Try(self, node: ast.Try) -> None:
            nonlocal complexity
            # Each except handler is a decision point
            complexity += max(1, len(node.handlers))
            self.generic_visit(node)

        def visit_Comprehension(self, node: ast.comprehension) -> None:  # type: ignore[override]
            nonlocal complexity
            # Each 'if' in a comprehension adds 1
            complexity += len(getattr(node, "ifs", []) or [])
            self.generic_visit(node)

        def visit_comprehension(self, node: ast.comprehension) -> None:
            # For older NodeVisitor patterns
            self.visit_Comprehension(node)

    Visitor().visit(fn)
    return complexity


def _collect_function_complexities(tree: ast.AST) -> List[FunctionComplexity]:
    funcs: List[FunctionComplexity] = []

    class FnVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            funcs.append(
                FunctionComplexity(
                    name=node.name,
                    lineno=node.lineno,
                    end_lineno=getattr(node, "end_lineno", None),
                    complexity=_cyclomatic_for_function(node),
                )
            )
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            funcs.append(
                FunctionComplexity(
                    name=node.name,
                    lineno=node.lineno,
                    end_lineno=getattr(node, "end_lineno", None),
                    complexity=_cyclomatic_for_function(node),
                )
            )
            self.generic_visit(node)

    FnVisitor().visit(tree)
    return funcs


PY_KEYWORD_OPERATORS = set(
    [
        # Flow control and logic keywords considered operators for Halstead
        "if",
        "elif",
        "else",
        "for",
        "while",
        "try",
        "except",
        "finally",
        "with",
        "as",
        "return",
        "yield",
        "lambda",
        "and",
        "or",
        "not",
        "is",
        "in",
        "pass",
        "break",
        "continue",
        "raise",
        "from",
        "await",
        "assert",
        "del",
        "global",
        "nonlocal",
        "match",
        "case",
    ]
)


def _halstead(path: Path) -> Dict[str, float]:
    src = _read_bytes(path)

    operators: Counter[str] = Counter()
    operands: Counter[str] = Counter()

    try:
        for tok in _iter_tokens(src):
            ttype = tok.type
            tstr = tok.string
            if ttype in (tokenize.ENCODING, tokenize.ENDMARKER, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT):
                continue
            if ttype == tokenize.COMMENT:
                continue
            if ttype == tokenize.OP:
                operators[tstr] += 1
                continue
            if ttype == tokenize.NAME:
                if keyword.iskeyword(tstr) and tstr in PY_KEYWORD_OPERATORS:
                    operators[tstr] += 1
                else:
                    operands[tstr] += 1
                continue
            if ttype in (tokenize.NUMBER, tokenize.STRING):
                operands[tstr] += 1
                continue
    except tokenize.TokenError:
        # Fallback: treat entire content as a single operand if tokenization fails
        operands["<unlexable>"] += 1

    n1 = float(len(operators))
    n2 = float(len(operands))
    N1 = float(sum(operators.values()))
    N2 = float(sum(operands.values()))
    vocabulary = n1 + n2
    length = N1 + N2
    volume = 0.0 if vocabulary <= 0 or length <= 0 else length * math.log2(vocabulary)
    difficulty = 0.0 if n2 == 0 else (n1 / 2.0) * (N2 / n2)
    effort = difficulty * volume
    bugs = volume / 3000.0 if volume > 0 else 0.0
    time = effort / 18.0 if effort > 0 else 0.0  # seconds

    return {
        "n1_distinct_operators": n1,
        "n2_distinct_operands": n2,
        "N1_total_operators": N1,
        "N2_total_operands": N2,
        "vocabulary": vocabulary,
        "length": length,
        "volume": volume,
        "difficulty": difficulty,
        "effort": effort,
        "time_seconds": time,
        "estimated_bugs": bugs,
        "operators": dict(operators),
        "operands": dict(operands),
    }


def _maintainability_index(volume: float, cyclomatic: int, sloc: int) -> float:
    # SEI/Visual Studio scaled variant (without comment weight):
    # MI = max(0, (171 - 5.2*ln(V) - 0.23*G - 16.2*ln(LOC))) * 100/171
    try:
        if volume <= 0 or sloc <= 0:
            return 100.0
        score = 171.0 - 5.2 * math.log(volume) - 0.23 * float(cyclomatic) - 16.2 * math.log(sloc)
        return max(0.0, min(100.0, (score * 100.0) / 171.0))
    except (ValueError, OverflowError):
        return 0.0


def analyze_file(file_path: str | Path) -> Dict:
    """
    Analyze a Python source file and return a metrics dictionary.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    loc = _count_loc(path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    warnings: List[str] = []
    try:
        tree = ast.parse(text)
        fn_complexities = _collect_function_complexities(tree)
        total_cyclomatic = sum(fc.complexity for fc in fn_complexities) or 1
    except SyntaxError:
        fn_complexities = []
        total_cyclomatic = 1
        warnings.append("SyntaxError: file could not be parsed; cyclomatic set to 1 and docstrings may be inaccurate.")

    hal = _halstead(path)
    mi = _maintainability_index(
        volume=float(hal.get("volume", 0.0)),
        cyclomatic=int(total_cyclomatic),
        sloc=int(loc.get("code", 0)),
    )

    return {
        "file_path": str(path),
        "language": "python",
        "summary": {
            "lines": loc["lines"],
            "code": loc["code"],
            "comments": loc["comments"],
            "blanks": loc["blanks"],
            "docstrings": loc["docstrings"],
        },
        "cyclomatic": {
            "total": int(total_cyclomatic),
            "by_function": [
                {
                    "name": fc.name,
                    "lineno": fc.lineno,
                    "end_lineno": fc.end_lineno,
                    "complexity": fc.complexity,
                }
                for fc in sorted(fn_complexities, key=lambda f: (f.complexity, f.lineno), reverse=True)
            ],
        },
        "halstead": {k: (float(v) if isinstance(v, (int, float)) else v) for k, v in hal.items()},
        "maintainability_index": float(mi),
        "warnings": warnings,
    }


def format_text_report(result: Dict) -> str:
    path = result.get("file_path", "<unknown>")
    s = result.get("summary", {})
    c = result.get("cyclomatic", {})
    h = result.get("halstead", {})
    mi = result.get("maintainability_index", 0.0)

    lines = []
    lines.append(f"File: {path}")
    lines.append("- Summary:")
    lines.append(
        f"  LOC={s.get('lines', 0)}  Code={s.get('code', 0)}  Comments={s.get('comments', 0)}  Blanks={s.get('blanks', 0)}  Docstrings={s.get('docstrings', 0)}"
    )
    lines.append("- Cyclomatic Complexity:")
    lines.append(f"  Total={c.get('total', 0)}")
    fns = c.get("by_function", [])
    if fns:
        lines.append("  By Function (top 10):")
        for fn in fns[:10]:
            lines.append(
                f"    {fn['name']} (L{fn['lineno']}{'-L'+str(fn['end_lineno']) if fn.get('end_lineno') else ''}): CC={fn['complexity']}"
            )
    lines.append("- Halstead:")
    lines.append(
        f"  n1={h.get('n1_distinct_operators',0):.0f} n2={h.get('n2_distinct_operands',0):.0f} N1={h.get('N1_total_operators',0):.0f} N2={h.get('N2_total_operands',0):.0f}"
    )
    lines.append(
        f"  vocab={h.get('vocabulary',0):.0f} length={h.get('length',0):.0f} volume={h.get('volume',0.0):.2f} difficulty={h.get('difficulty',0.0):.2f}"
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

