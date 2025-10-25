import json
import sys
from pathlib import Path
from textwrap import dedent

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from complexity_analyzer.__main__ import main
from complexity_analyzer.core import analyze_file, available_languages, detect_language, format_text_report


def test_available_languages_are_sorted_and_known():
    langs = available_languages()
    assert langs == ["java", "python"]


@pytest.mark.parametrize(
    "filename, expected",
    [
        ("example.py", "python"),
        ("Example.JAVA", "java"),
        ("unknown.txt", None),
    ],
)
def test_detect_language_from_extension(tmp_path, filename, expected):
    path = tmp_path / filename
    path.write_text("print('hello')\n")
    assert detect_language(path) == expected


@pytest.fixture()
def sample_python_file(tmp_path) -> Path:
    content = dedent(
        '''\
        """Module docstring"""

        # A comment

        def foo(x):
            """Docstring for foo."""
            if x > 0:
                return x
            else:
                return -x
        '''
    )
    path = tmp_path / "sample.py"
    path.write_text(content)
    return path


@pytest.fixture()
def sample_java_file(tmp_path) -> Path:
    content = "\n".join(
        [
            "package demo;",
            "",
            "public class Example {",
            "    /* Block comment",
            "       continues */",
            "    // Single line",
            "    public int compute(int a, int b) {",
            "        int sum = a + b;",
            "        if (sum > 10 && a > 0) {",
            "            return sum;",
            "        } else if (sum == 0) {",
            "            return 0;",
            "        }",
            "        return sum - 1;",
            "    }",
            "}",
            "",
        ]
    )
    path = tmp_path / "Example.java"
    path.write_text(content)
    return path


def test_analyze_python_file_reports_expected_metrics(sample_python_file):
    result = analyze_file(sample_python_file)

    assert result["language"] == "python"

    summary = result["summary"]
    assert summary == {
        "lines": 10,
        "code": 5,
        "comments": 1,
        "blanks": 2,
        "docstrings": 2,
    }

    cyclomatic = result["cyclomatic"]
    assert cyclomatic["total"] == 2
    assert cyclomatic["by_function"][0]["name"] == "foo"
    assert cyclomatic["by_function"][0]["complexity"] == 2

    halstead = result["halstead"]
    assert halstead["vocabulary"] > 0
    assert halstead["length"] > 0

    mi = result["maintainability_index"]
    assert 0.0 <= mi <= 100.0

    report = format_text_report(result)
    assert f"File: {sample_python_file}" in report
    assert "Language: Python" in report
    assert "LOC=10  Code=5  Comments=1  Blanks=2  Docstrings=2" in report
    assert "Cyclomatic" in report
    assert "Maintainability Index" in report


def test_analyze_python_file_with_syntax_error_reports_warning(tmp_path):
    path = tmp_path / "broken.py"
    path.write_text("def broken()\n    pass\n")

    result = analyze_file(path)

    assert result["language"] == "python"
    assert result["cyclomatic"]["total"] == 1
    assert result["cyclomatic"]["by_function"] == []

    warnings = result["warnings"]
    assert warnings
    assert "SyntaxError" in warnings[0]

    summary = result["summary"]
    assert summary["lines"] == 2
    assert summary["code"] == 2
    assert summary["comments"] == 0
    assert summary["docstrings"] == 0


def test_analyze_java_file_reports_expected_metrics(sample_java_file):
    result = analyze_file(sample_java_file)

    assert result["language"] == "java"

    summary = result["summary"]
    assert summary == {
        "lines": 16,
        "code": 12,
        "comments": 3,
        "blanks": 1,
        "docstrings": 0,
    }

    cyclomatic = result["cyclomatic"]
    assert cyclomatic["total"] == 4
    assert cyclomatic["by_function"] == []

    halstead = result["halstead"]
    assert halstead["vocabulary"] > 0
    assert halstead["length"] > 0

    mi = result["maintainability_index"]
    assert 0.0 <= mi <= 100.0


def test_cli_json_output_omits_operand_maps(sample_python_file, capsys):
    exit_code = main([str(sample_python_file), "--format", "json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "operators" not in data["halstead"]
    assert "operands" not in data["halstead"]
