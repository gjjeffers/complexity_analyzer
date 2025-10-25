from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

from .base import BaseAnalyzer, maintainability_index


JAVA_KEYWORDS = {
    "abstract",
    "assert",
    "boolean",
    "break",
    "byte",
    "case",
    "catch",
    "char",
    "class",
    "const",
    "continue",
    "default",
    "do",
    "double",
    "else",
    "enum",
    "extends",
    "final",
    "finally",
    "float",
    "for",
    "goto",
    "if",
    "implements",
    "import",
    "instanceof",
    "int",
    "interface",
    "long",
    "native",
    "new",
    "package",
    "private",
    "protected",
    "public",
    "return",
    "short",
    "static",
    "strictfp",
    "super",
    "switch",
    "synchronized",
    "this",
    "throw",
    "throws",
    "transient",
    "try",
    "void",
    "volatile",
    "while",
    "record",
    "sealed",
    "permits",
    "var",
    "yield",
}

JAVA_LITERAL_KEYWORDS = {"true", "false", "null"}
JAVA_OPERATOR_KEYWORDS = JAVA_KEYWORDS - JAVA_LITERAL_KEYWORDS

JAVA_OPERATORS = {
    "+",
    "-",
    "*",
    "/",
    "%",
    "++",
    "--",
    "==",
    "!=",
    ">",
    "<",
    ">=",
    "<=",
    "&&",
    "||",
    "!",
    "~",
    "&",
    "|",
    "^",
    "<<",
    ">>",
    ">>>",
    "+=",
    "-=",
    "*=",
    "/=",
    "%=",
    "&=",
    "|=",
    "^=",
    "<<=",
    ">>=",
    ">>>=",
    "=",
    "?",
    ":",
    "->",
    "::",
    ".",
    ",",
    ";",
    "(",
    ")",
    "{",
    "}",
    "[",
    "]",
}

MULTI_CHAR_OPERATORS = sorted(
    [
        ">>>=",
        "<<=",
        ">>=",
        ">>>",
        "&&",
        "||",
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
        "++",
        "--",
        "->",
        "::",
    ],
    key=len,
    reverse=True,
)

DECISION_KEYWORDS = {"if", "for", "while", "case", "catch", "switch", "do"}


class JavaAnalyzer(BaseAnalyzer):
    language = "java"
    extensions = {".java"}

    def analyze(self, path: Path) -> Dict:
        if not path.exists():
            raise FileNotFoundError(str(path))

        text = path.read_text(encoding="utf-8", errors="ignore")
        loc = _java_loc_metrics(text)
        cleaned = _strip_comments(text)
        tokens = list(_tokenize_java(cleaned))
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


def _java_loc_metrics(text: str) -> Dict[str, int]:
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
        line_has_code = False
        line_has_comment = block_comment
        in_string = False
        in_char = False

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

            if in_string:
                if ch == "\\":
                    i += 2
                elif ch == '"':
                    in_string = False
                    i += 1
                else:
                    i += 1
                continue

            if in_char:
                if ch == "\\":
                    i += 2
                elif ch == "'":
                    in_char = False
                    i += 1
                else:
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
            if ch == '"':
                in_string = True
                line_has_code = True
                i += 1
                continue
            if ch == "'":
                in_char = True
                line_has_code = True
                i += 1
                continue
            if not ch.isspace():
                line_has_code = True
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
    in_string = False
    in_char = False

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

        if in_string:
            result.append(ch)
            if ch == "\\" and i + 1 < n:
                result.append(text[i + 1])
                i += 2
            elif ch == '"':
                in_string = False
                i += 1
            else:
                i += 1
            continue

        if in_char:
            result.append(ch)
            if ch == "\\" and i + 1 < n:
                result.append(text[i + 1])
                i += 2
            elif ch == "'":
                in_char = False
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

        if ch == '"':
            in_string = True
            result.append(ch)
            i += 1
            continue

        if ch == "'":
            in_char = True
            result.append(ch)
            i += 1
            continue

        result.append(ch)
        i += 1

    return "".join(result)


def _tokenize_java(text: str) -> Iterable[str]:
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

        if ch.isalpha() or ch == "_" or ch == "$":
            start = i
            i += 1
            while i < n and (text[i].isalnum() or text[i] in ("_", "$")):
                i += 1
            tokens.append(text[start:i])
            continue

        if ch.isdigit():
            start = i
            i += 1
            while i < n and (text[i].isalnum() or text[i] in ("_", ".", "x", "X", "p", "P", "+", "-")):
                # Rough handling for numeric literals including hex, binary, floats
                i += 1
            tokens.append(text[start:i])
            continue

        if ch == '"' or ch == "'":
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

        tokens.append(ch)
        i += 1
    return tokens


def _cyclomatic_complexity(tokens: List[str]) -> int:
    complexity = 1
    for idx, tok in enumerate(tokens):
        if tok in DECISION_KEYWORDS:
            complexity += 1
        elif tok == "?":
            complexity += 1
        elif tok in {"&&", "||"}:
            complexity += 1
    return complexity


def _halstead_metrics(tokens: Iterable[str]) -> Dict[str, float]:
    operators: Counter[str] = Counter()
    operands: Counter[str] = Counter()

    for tok in tokens:
        if not tok:
            continue
        if tok in JAVA_LITERAL_KEYWORDS:
            operands[tok] += 1
        elif tok in JAVA_OPERATOR_KEYWORDS or tok in JAVA_OPERATORS:
            operators[tok] += 1
        elif tok[0] in ('"', "'"):
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
