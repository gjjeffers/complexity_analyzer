# Complexity Analyzer

## Overview

Complexity Analyzer is a lightweight static analysis utility that extracts code metrics from individual Python files. It focuses on signal-rich metrics that are often used in code review or maintainability audits, such as lines-of-code breakdowns, cyclomatic complexity, Halstead metrics, and the SEI maintainability index. The tool is designed to be dependency-free, fast to run on a single file, and easy to integrate into other automation, including AI agents that need structured code quality signals.

### Key Features
- **Line counting** – total lines, logical code lines, comment lines, blank lines, and docstring lines.
- **Cyclomatic complexity** – per-function and aggregated counts to highlight hotspots.
- **Halstead metrics** – operator/operand vocabulary, volume, difficulty, effort, and bug/time estimates.
- **Maintainability index** – Visual Studio style index scaled from 0–100.
- **Warning surface** – parse errors and other anomalies are reported alongside metric output.

## Installation

This repository is self-contained and only relies on the Python standard library. Clone it and, if you prefer an isolated interpreter, create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
```

Run the module directly from the repository root to use the CLI without any packaging step:

```bash
python -m complexity_analyzer --help
```

## Usage

### Command-line interface

Run the analyzer on a Python source file by passing the file path. Choose between a human-friendly text report (default) and JSON output.

```bash
python -m complexity_analyzer path/to/file.py
python -m complexity_analyzer path/to/file.py --format json
python -m complexity_analyzer path/to/file.py --format json --show-operands
```

- `--format text` (default) prints a multi-section summary of line counts, cyclomatic complexity, Halstead metrics, and maintainability index.
- `--format json` serializes the analysis dictionary as JSON. By default, the potentially large `operators` and `operands` maps are omitted to keep the payload small.
- `--show-operands` restores the full Halstead `operators` and `operands` breakdown when using JSON output.

The CLI exits with status code `0` on success and `2` when the provided file is not found.

### Programmatic usage

You can also call the analysis functions from Python code:

```python
from complexity_analyzer.core import analyze_file, format_text_report

result = analyze_file("path/to/file.py")
print(result["summary"]["code"], "source lines of code")
print(format_text_report(result))
```

`analyze_file` returns a dictionary with the same structure as the JSON output, making it easy to integrate into other tooling or AI pipelines.

## Output structure

The analysis dictionary contains the following top-level keys:

| Key | Description |
| --- | --- |
| `file_path` | Absolute or relative path to the analyzed file. |
| `language` | Detected language identifier. Currently always `"python"`. |
| `summary` | Counts for total lines, code, comments, blanks, and docstrings. |
| `cyclomatic` | Total cyclomatic complexity and a per-function breakdown. |
| `halstead` | Distinct/total operator and operand counts, vocabulary, length, volume, difficulty, effort, estimated defects, and optional operator/operand maps. |
| `maintainability_index` | Scaled maintainability score between 0 and 100. |
| `warnings` | List of parse or analysis warnings. |

## Supported languages

- Python (`.py` files)

Additional languages are not yet supported. Contributions extending the tokenizer and metric collectors for other languages are welcome.

## Integration tips for AI agents

- Prefer JSON output for machine ingestion. It provides numeric values and structured sub-sections that are easy to parse.
- Use the `summary.code` count as a proxy for file size before running more expensive analyses.
- Review `cyclomatic.by_function` to prioritize complex functions for refactoring suggestions.
- Watch for non-empty `warnings` and handle them explicitly in downstream workflows.

## License

This project is licensed under the terms of the [MIT License](LICENSE).

