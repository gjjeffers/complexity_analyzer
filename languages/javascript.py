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

_REGEX_PREFIX_KEYWORDS = {
    "return",
    "case",
    "throw",
    "default",
    "do",
    "else",
    "typeof",
    "delete",
    "void",
    "instanceof",
    "in",
    "of",
    "new",
    "await",
    "yield",
}

_CONTROL_FLOW_KEYWORDS = {"if", "while", "for", "with", "switch", "catch"}

_REGEX_FLAG_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")

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


def _consume_js_identifier(text: str, start: int) -> int:
    i = start + 1
    n = len(text)
    while i < n and (text[i].isalnum() or text[i] in ("_", "$")):
        i += 1
    return i


def _consume_js_number(text: str, start: int) -> int:
    i = start + 1
    n = len(text)
    while i < n and (
        text[i].isalnum()
        or text[i]
        in (
            "_",
            ".",
            "x",
            "X",
            "b",
            "B",
            "o",
            "O",
            "e",
            "E",
            "+",
            "-",
        )
    ):
        i += 1
    return i


def _consume_regex_literal(text: str, start: int) -> int | None:
    i = start + 1
    n = len(text)
    escaped = False
    in_class = False

    while i < n:
        ch = text[i]
        if ch == "\n":
            return None
        if escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == "[":
            in_class = True
        elif ch == "]" and in_class:
            in_class = False
        elif ch == "/" and not in_class:
            if i == start + 1:
                return None
            i += 1
            while i < n and text[i] in _REGEX_FLAG_CHARS:
                i += 1
            return i
        i += 1

    return None


def _is_regex_literal(token: str) -> bool:
    if len(token) < 3 or token[0] != "/":
        return False

    escaped = False
    in_class = False

    for i in range(1, len(token)):
        ch = token[i]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "[":
            in_class = True
            continue
        if ch == "]" and in_class:
            in_class = False
            continue
        if ch == "/" and not in_class:
            if i == 1:
                return False
            flags = token[i + 1 :]
            return all(flag in _REGEX_FLAG_CHARS for flag in flags)
    return False


def _initial_js_context() -> Dict[str, object]:
    return {
        "last": "start",
        "pending_control": None,
        "paren_stack": [],
    }


def _can_start_regex(context: Dict[str, object]) -> bool:
    return context["last"] in {"start", "after_operator"}


def _set_after_operator(context: Dict[str, object]) -> None:
    context["last"] = "after_operator"
    # keep pending_control for constructs like "if" before "("


def _set_after_operand(context: Dict[str, object]) -> None:
    context["last"] = "after_operand"
    context["pending_control"] = None


def _handle_identifier(context: Dict[str, object], identifier: str) -> None:
    if identifier in _CONTROL_FLOW_KEYWORDS:
        context["pending_control"] = identifier
        context["last"] = "after_operator"
    elif identifier in _REGEX_PREFIX_KEYWORDS:
        context["pending_control"] = None
        context["last"] = "after_operator"
    else:
        _set_after_operand(context)


def _handle_open_paren(context: Dict[str, object]) -> None:
    stack = context["paren_stack"]
    if context["pending_control"]:
        stack.append(("control", context["pending_control"]))
        context["pending_control"] = None
    else:
        stack.append(("group", None))
    _set_after_operator(context)


def _handle_close_paren(context: Dict[str, object]) -> None:
    stack = context["paren_stack"]
    if stack:
        kind, _ = stack.pop()
        if kind == "control":
            _set_after_operator(context)
        else:
            _set_after_operand(context)
    else:
        _set_after_operand(context)
    context["pending_control"] = None


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
    blank_lines = sum(1 for line in lines if not line.strip())
    comment_lines: Set[int] = set()

    context = _initial_js_context()
    in_block = False
    in_string: str | None = None
    in_template = False

    i = 0
    n = len(text)
    line_no = 1

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_block:
            comment_lines.add(line_no)
            if ch == "\n":
                line_no += 1
                i += 1
                continue
            if ch == "*" and nxt == "/":
                comment_lines.add(line_no)
                in_block = False
                i += 2
            else:
                i += 1
            continue

        if in_template:
            if ch == "\n":
                line_no += 1
            if ch == "\\" and nxt:
                i += 2
                continue
            if ch == "`":
                in_template = False
                _set_after_operand(context)
            i += 1
            continue

        if in_string:
            if ch == "\n":
                line_no += 1
            if ch == "\\" and nxt:
                i += 2
                continue
            if ch == in_string:
                in_string = None
                _set_after_operand(context)
            i += 1
            continue

        if ch.isspace():
            if ch == "\n":
                line_no += 1
                _set_after_operator(context)
            i += 1
            continue

        if ch == "/" and nxt == "*":
            comment_lines.add(line_no)
            in_block = True
            i += 2
            continue

        if ch == "/" and nxt == "/":
            if _can_start_regex(context):
                regex_end = _consume_regex_literal(text, i)
                if regex_end is not None:
                    i = regex_end
                    _set_after_operand(context)
                    continue
            comment_lines.add(line_no)
            i += 2
            while i < n and text[i] != "\n":
                i += 1
            _set_after_operator(context)
            continue

        if _can_start_regex(context):
            regex_end = _consume_regex_literal(text, i)
            if regex_end is not None:
                i = regex_end
                _set_after_operand(context)
                continue

        if ch in {'"', "'"}:
            in_string = ch
            i += 1
            continue

        if ch == "`":
            in_template = True
            i += 1
            continue

        if ch.isalpha() or ch in ("_", "$"):
            end = _consume_js_identifier(text, i)
            identifier = text[i:end]
            _handle_identifier(context, identifier)
            i = end
            continue

        if ch.isdigit():
            end = _consume_js_number(text, i)
            _set_after_operand(context)
            i = end
            continue

        matched = False
        for op in MULTI_CHAR_OPERATORS:
            if text.startswith(op, i):
                i += len(op)
                if op in {"++", "--"} and context["last"] == "after_operand":
                    _set_after_operand(context)
                else:
                    _set_after_operator(context)
                matched = True
                break
        if matched:
            continue

        if ch == "(":
            _handle_open_paren(context)
            i += 1
            continue

        if ch == ")":
            _handle_close_paren(context)
            i += 1
            continue

        if ch in "[{":
            _set_after_operator(context)
            i += 1
            continue

        if ch in "}]":
            _set_after_operand(context)
            i += 1
            continue

        if ch in ";,?:":
            _set_after_operator(context)
            i += 1
            continue

        if ch == ".":
            _set_after_operand(context)
            i += 1
            continue

        _set_after_operator(context)
        i += 1

    sloc = max(0, total - blank_lines - len(comment_lines))

    return {
        "lines": total,
        "code": sloc,
        "comments": len(comment_lines),
        "blanks": blank_lines,
    }


def _strip_template_expression(text: str, start: int) -> tuple[str, int]:
    """Strip a template literal expression starting at ``text[start] == "{"``.

    The returned string includes the surrounding braces and any comments inside
    the expression are replaced with whitespace so downstream tokenization can
    safely process the embedded code. The second return value is the index just
    past the closing brace.
    """

    result: List[str] = []
    i = start
    n = len(text)
    depth = 0
    in_block = False
    in_string: str | None = None
    in_template = False
    context = _initial_js_context()

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_block:
            if ch == "\n":
                result.append("\n")
                i += 1
                continue
            if ch == "*" and nxt == "/":
                result.append("  ")
                in_block = False
                i += 2
            else:
                result.append(" ")
                i += 1
            continue

        if in_template:
            if ch == "$" and nxt == "{":
                expr, i = _strip_template_expression(text, i + 1)
                result.append("$")
                result.append(expr)
                continue
            result.append(ch)
            if ch == "\n":
                i += 1
                continue
            if ch == "\\" and nxt:
                result.append(text[i + 1])
                i += 2
                continue
            if ch == "`":
                in_template = False
                _set_after_operand(context)
            i += 1
            continue

        if in_string:
            result.append(ch)
            if ch == "\n":
                i += 1
                continue
            if ch == "\\" and nxt:
                result.append(text[i + 1])
                i += 2
                continue
            if ch == in_string:
                in_string = None
                _set_after_operand(context)
            i += 1
            continue

        if ch.isspace():
            result.append(ch)
            if ch == "\n":
                _set_after_operator(context)
            i += 1
            continue

        if ch == "/" and nxt == "*":
            result.append("  ")
            in_block = True
            i += 2
            continue

        if ch == "/" and nxt == "/":
            if _can_start_regex(context):
                regex_end = _consume_regex_literal(text, i)
                if regex_end is not None:
                    literal = text[i:regex_end]
                    result.append(literal)
                    i = regex_end
                    _set_after_operand(context)
                    continue
            result.append("  ")
            i += 2
            while i < n and text[i] != "\n":
                result.append(" ")
                i += 1
            continue

        if _can_start_regex(context):
            regex_end = _consume_regex_literal(text, i)
            if regex_end is not None:
                literal = text[i:regex_end]
                result.append(literal)
                i = regex_end
                _set_after_operand(context)
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

        if ch == "{":
            depth += 1
            result.append(ch)
            _set_after_operator(context)
            i += 1
            continue

        if ch == "}":
            result.append(ch)
            i += 1
            _set_after_operand(context)
            depth -= 1
            if depth <= 0:
                break
            continue

        if ch.isalpha() or ch in ("_", "$"):
            end = _consume_js_identifier(text, i)
            identifier = text[i:end]
            result.append(identifier)
            _handle_identifier(context, identifier)
            i = end
            continue

        if ch.isdigit():
            end = _consume_js_number(text, i)
            result.append(text[i:end])
            _set_after_operand(context)
            i = end
            continue

        result.append(ch)
        if ch == "(":
            _handle_open_paren(context)
        elif ch == ")":
            _handle_close_paren(context)
        elif ch in "[{":
            _set_after_operator(context)
        elif ch in "]}":
            _set_after_operand(context)
        elif ch in ";,?:":
            _set_after_operator(context)
        elif ch == ".":
            _set_after_operand(context)
        else:
            _set_after_operator(context)
        i += 1

    return "".join(result), i


def _strip_comments(text: str) -> str:
    result: List[str] = []
    i = 0
    n = len(text)
    in_block = False
    in_string: str | None = None
    in_template = False
    context = _initial_js_context()

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_block:
            if ch == "\n":
                result.append("\n")
                i += 1
                continue
            if ch == "*" and nxt == "/":
                result.append("  ")
                in_block = False
                i += 2
            else:
                result.append(" ")
                i += 1
            continue

        if in_template:
            if ch == "$" and nxt == "{":
                expr, i = _strip_template_expression(text, i + 1)
                result.append("$")
                result.append(expr)
                continue
            result.append(ch)
            if ch == "\n":
                i += 1
                continue
            if ch == "\\" and nxt:
                result.append(text[i + 1])
                i += 2
                continue
            if ch == "`":
                in_template = False
                _set_after_operand(context)
            i += 1
            continue

        if in_string:
            result.append(ch)
            if ch == "\n":
                i += 1
                continue
            if ch == "\\" and nxt:
                result.append(text[i + 1])
                i += 2
                continue
            if ch == in_string:
                in_string = None
                _set_after_operand(context)
            i += 1
            continue

        if ch.isspace():
            result.append(ch)
            if ch == "\n":
                _set_after_operator(context)
            i += 1
            continue

        if ch == "/" and nxt == "*":
            result.append("  ")
            in_block = True
            i += 2
            continue

        if ch == "/" and nxt == "/":
            if _can_start_regex(context):
                regex_end = _consume_regex_literal(text, i)
                if regex_end is not None:
                    literal = text[i:regex_end]
                    result.append(literal)
                    i = regex_end
                    _set_after_operand(context)
                    continue
            result.append("  ")
            i += 2
            while i < n and text[i] != "\n":
                result.append(" ")
                i += 1
            continue

        if _can_start_regex(context):
            regex_end = _consume_regex_literal(text, i)
            if regex_end is not None:
                literal = text[i:regex_end]
                result.append(literal)
                i = regex_end
                _set_after_operand(context)
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

        if ch.isalpha() or ch in ("_", "$"):
            end = _consume_js_identifier(text, i)
            identifier = text[i:end]
            result.append(identifier)
            _handle_identifier(context, identifier)
            i = end
            continue

        if ch.isdigit():
            end = _consume_js_number(text, i)
            result.append(text[i:end])
            _set_after_operand(context)
            i = end
            continue

        matched = False
        for op in MULTI_CHAR_OPERATORS:
            if text.startswith(op, i):
                result.append(op)
                i += len(op)
                if op in {"++", "--"} and context["last"] == "after_operand":
                    _set_after_operand(context)
                else:
                    _set_after_operator(context)
                matched = True
                break
        if matched:
            continue

        result.append(ch)
        if ch == "(":
            _handle_open_paren(context)
        elif ch == ")":
            _handle_close_paren(context)
        elif ch in "[{":
            _set_after_operator(context)
        elif ch in "}]":
            _set_after_operand(context)
        elif ch in ";,?:":
            _set_after_operator(context)
        elif ch == ".":
            _set_after_operand(context)
        else:
            _set_after_operator(context)
        i += 1

    return "".join(result)


def _tokenize_js(text: str) -> Iterable[str]:
    tokens: List[str] = []
    i = 0
    n = len(text)
    context = _initial_js_context()

    while i < n:
        ch = text[i]
        if ch.isspace():
            if ch == "\n":
                _set_after_operator(context)
            i += 1
            continue

        if ch == "/" and _can_start_regex(context):
            regex_end = _consume_regex_literal(text, i)
            if regex_end is not None:
                tokens.append(text[i:regex_end])
                i = regex_end
                _set_after_operand(context)
                continue

        matched = False
        for op in MULTI_CHAR_OPERATORS:
            if text.startswith(op, i):
                tokens.append(op)
                i += len(op)
                if op in {"++", "--"} and context["last"] == "after_operand":
                    _set_after_operand(context)
                else:
                    _set_after_operator(context)
                matched = True
                break
        if matched:
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
                if curr == "\n":
                    break
                i += 1
            tokens.append(text[start:i])
            _set_after_operand(context)
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
                    expr_text, new_index = _strip_template_expression(text, i + 1)
                    body = expr_text[1:-1] if len(expr_text) > 1 else ""
                    if body:
                        expressions.append(body)
                    i = new_index
                    continue
                if curr == "`":
                    i += 1
                    break
                i += 1
            tokens.append(text[start:i])
            for expr in expressions:
                tokens.extend(_tokenize_js(expr))
            _set_after_operand(context)
            continue

        if ch.isalpha() or ch in ("_", "$"):
            end = _consume_js_identifier(text, i)
            identifier = text[i:end]
            tokens.append(identifier)
            _handle_identifier(context, identifier)
            i = end
            continue

        if ch.isdigit():
            end = _consume_js_number(text, i)
            tokens.append(text[i:end])
            _set_after_operand(context)
            i = end
            continue

        tokens.append(ch)
        if ch == "(":
            _handle_open_paren(context)
        elif ch == ")":
            _handle_close_paren(context)
        elif ch in "[{":
            _set_after_operator(context)
        elif ch in "}]":
            _set_after_operand(context)
        elif ch in ";,?:":
            _set_after_operator(context)
        elif ch == ".":
            _set_after_operand(context)
        else:
            _set_after_operator(context)
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
        elif _is_regex_literal(tok):
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
