from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Set

from .base import BaseAnalyzer, maintainability_index


JS_KEYWORDS = {
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "debugger",
    "default",
    "delete",
    "do",
    "else",
    "export",
    "extends",
    "finally",
    "for",
    "function",
    "if",
    "import",
    "in",
    "instanceof",
    "let",
    "new",
    "return",
    "super",
    "switch",
    "this",
    "throw",
    "try",
    "typeof",
    "var",
    "void",
    "while",
    "with",
    "yield",
    "await",
    "enum",
    "implements",
    "interface",
    "package",
    "private",
    "protected",
    "public",
    "static",
    "async",
    "of",
}

JS_LITERAL_KEYWORDS = {"true", "false", "null", "undefined", "NaN", "Infinity"}
JS_OPERATOR_KEYWORDS = JS_KEYWORDS - JS_LITERAL_KEYWORDS

JS_OPERATORS = {
    "+",
    "-",
    "*",
    "/",
    "%",
    "**",
    "++",
    "--",
    "=",
    "+=",
    "-=",
    "*=",
    "/=",
    "%=",
    "**=",
    "<<",
    ">>",
    ">>>",
    "<<=",
    ">>=",
    ">>>=",
    "&",
    "|",
    "^",
    "~",
    "&=",
    "|=",
    "^=",
    "&&",
    "||",
    "??",
    "&&=",
    "||=",
    "??=",
    "!",
    "==",
    "!=",
    "===",
    "!==",
    ">",
    "<",
    ">=",
    "<=",
    "=>",
    "?",
    ":",
    ",",
    ".",
    "...",
    "(",
    ")",
    "{",
    "}",
    "[",
    "]",
    ";",
}

MULTI_CHAR_OPERATORS = sorted(
    [
        "??=",
        "&&=",
        "||=",
        "**=",
        ">>>=",
        "<<=",
        ">>=",
        "===",
        "!==",
        "**",
        "&&",
        "||",
        "??",
        "==",
        "!=",
        ">=",
        "<=",
        "+=",
        "-=",
        "*=",
        "/=",
        "%=",
        "&=",
        "|=",
        "^=",
        "<<",
        ">>",
        ">>>",
        "++",
        "--",
        "=>",
        "...",
    ],
    key=len,
    reverse=True,
)

DECISION_KEYWORDS = {"if", "for", "while", "case", "catch", "switch", "do"}


class JavaScriptAnalyzer(BaseAnalyzer):
    language = "javascript"
    extensions = {".js", ".jsx", ".mjs", ".cjs"}

    def analyze(self, path: Path) -> Dict:
        if not path.exists():
            raise FileNotFoundError(str(path))

        text = path.read_text(encoding="utf-8", errors="ignore")
        loc = _js_loc_metrics(text)
        cleaned = _strip_comments(text)
        tokens = list(_tokenize_js(cleaned))
        cyclomatic = _cyclomatic_complexity(tokens)
        halstead = _halstead_metrics(tokens)
        mi = maintainability_index(
            volume=float(halstead.get("volume", 0.0)),
            cyclomatic=int(cyclomatic),
            sloc=int(loc.get("code", 0)),
        )

        return {
            "file_path": str(path),
            "language": self.language,
            "summary": {
                "lines": loc["lines"],
                "code": loc["code"],
                "comments": loc["comments"],
                "blanks": loc["blanks"],
                "docstrings": 0,
            },
            "cyclomatic": {
                "total": int(cyclomatic),
                "by_function": [],
            },
            "halstead": halstead,
            "maintainability_index": float(mi),
            "warnings": [],
        }


def _js_loc_metrics(text: str) -> Dict[str, int]:
    lines = text.splitlines()
    total = len(lines)
    blank_lines = 0
    comment_lines: Set[int] = set()

    block_comment = False
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            blank_lines += 1

        i = 0
        length = len(line)
        line_has_comment = block_comment
        in_string: str | None = None
        in_template = False

        while i < length:
            ch = line[i]
            nxt = line[i + 1] if i + 1 < length else ""

            if block_comment:
                line_has_comment = True
                if ch == "*" and nxt == "/":
                    block_comment = False
                    i += 2
                else:
                    i += 1
                continue

            if in_template:
                if ch == "\\" and nxt:
                    i += 2
                    continue
                if ch == "`":
                    in_template = False
                i += 1
                continue

            if in_string:
                if ch == "\\" and nxt:
                    i += 2
                    continue
                if ch == in_string:
                    in_string = None
                i += 1
                continue

            if ch == "/" and nxt == "/":
                line_has_comment = True
                break
            if ch == "/" and nxt == "*":
                block_comment = True
                line_has_comment = True
                i += 2
                continue
            if ch in {'"', "'"}:
                in_string = ch
                i += 1
                continue
            if ch == "`":
                in_template = True
                i += 1
                continue
            i += 1

        if line_has_comment:
            comment_lines.add(idx)

    sloc = max(0, total - blank_lines - len(comment_lines))

    return {
        "lines": total,
        "code": sloc,
        "comments": len(comment_lines),
        "blanks": blank_lines,
    }


def _strip_comments(text: str) -> str:
    result: List[str] = []
    i = 0
    n = len(text)
    in_block = False
    in_string: str | None = None
    in_template = False

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_block:
            if ch == "*" and nxt == "/":
                result.append("  ")
                in_block = False
                i += 2
            else:
                result.append("\n" if ch == "\n" else " ")
                i += 1
            continue

        if in_template:
            result.append(ch)
            if ch == "\\" and i + 1 < n:
                result.append(text[i + 1])
                i += 2
            elif ch == "`":
                in_template = False
                i += 1
            else:
                i += 1
            continue

        if in_string:
            result.append(ch)
            if ch == "\\" and i + 1 < n:
                result.append(text[i + 1])
                i += 2
            elif ch == in_string:
                in_string = None
                i += 1
            else:
                i += 1
            continue

        if ch == "/" and nxt == "/":
            result.append("  ")
            i += 2
            while i < n and text[i] != "\n":
                result.append(" ")
                i += 1
            continue

        if ch == "/" and nxt == "*":
            result.append("  ")
            in_block = True
            i += 2
            continue

        if ch in {'"', "'"}:
            in_string = ch
            result.append(ch)
            i += 1
            continue

        if ch == "`":
            in_template = True
            result.append(ch)
            i += 1
            continue

        result.append(ch)
        i += 1

    return "".join(result)


def _tokenize_js(text: str) -> Iterable[str]:
    tokens: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue

        matched = False
        for op in MULTI_CHAR_OPERATORS:
            if text.startswith(op, i):
                tokens.append(op)
                i += len(op)
                matched = True
                break
        if matched:
            continue

        if ch.isalpha() or ch in ("_", "$"):
            start = i
            i += 1
            while i < n and (text[i].isalnum() or text[i] in ("_", "$")):
                i += 1
            tokens.append(text[start:i])
            continue

        if ch.isdigit():
            start = i
            i += 1
            while i < n and (text[i].isalnum() or text[i] in ("_", ".", "x", "X", "b", "B", "o", "O", "e", "E", "+", "-")):
                i += 1
            tokens.append(text[start:i])
            continue

        if ch in {'"', "'"}:
            delimiter = ch
            start = i
            i += 1
            while i < n:
                curr = text[i]
                if curr == "\\" and i + 1 < n:
                    i += 2
                    continue
                if curr == delimiter:
                    i += 1
                    break
                i += 1
            tokens.append(text[start:i])
            continue

        if ch == "`":
            start = i
            i += 1
            expressions: List[str] = []
            while i < n:
                curr = text[i]
                if curr == "\\" and i + 1 < n:
                    i += 2
                    continue
                if curr == "$" and i + 1 < n and text[i + 1] == "{":
                    i += 2
                    expr_start = i
                    depth = 1
                    while i < n and depth > 0:
                        curr = text[i]
                        if curr == "\\" and i + 1 < n:
                            i += 2
                            continue
                        if curr == "{":
                            depth += 1
                            i += 1
                            continue
                        if curr == "}":
                            depth -= 1
                            if depth == 0:
                                expressions.append(text[expr_start:i])
                                i += 1
                                break
                            i += 1
                            continue
                        i += 1
                    continue
                if curr == "`":
                    i += 1
                    break
                i += 1
            tokens.append(text[start:i])
            for expr in expressions:
                tokens.extend(_tokenize_text(expr))
            continue

        tokens.append(ch)
        i += 1

    return tokens


def _cyclomatic_complexity(tokens: List[str]) -> int:
    complexity = 1
    for tok in tokens:
        if tok in DECISION_KEYWORDS:
            complexity += 1
        elif tok == "?":
            complexity += 1
        elif tok in {"&&", "||", "??"}:
            complexity += 1
    return complexity


def _halstead_metrics(tokens: Iterable[str]) -> Dict[str, float]:
    operators: Counter[str] = Counter()
    operands: Counter[str] = Counter()

    for tok in tokens:
        if not tok:
            continue
        if tok in JS_LITERAL_KEYWORDS:
            operands[tok] += 1
        elif tok in JS_OPERATOR_KEYWORDS or tok in JS_OPERATORS:
            operators[tok] += 1
        elif tok[0] in {'"', "'", "`"}:
            operands[tok] += 1
        elif tok[0].isdigit():
            operands[tok] += 1
        elif tok[0].isalpha() or tok[0] in ("_", "$"):
            operands[tok] += 1
        else:
            operators[tok] += 1

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
    time = effort / 18.0 if effort > 0 else 0.0

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
