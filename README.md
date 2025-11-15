# Complexity Analyzer

Complexity Analyzer is a lightweight static analysis toolkit that reports
maintainability metrics for source files. It currently supports Python, Java,
JavaScript, and TypeScript code, producing:

* Source line counts (total, code, comment, blank, and docstring lines)
* Cyclomatic complexity totals (with per-function detail for Python)
* Halstead metrics (length, vocabulary, effort, estimated bugs, and more)
* Maintainability Index scores on a 0–100 scale

The library powers a simple command line interface so you can inspect metrics
quickly while developing.

## Installation

The package is intentionally self-contained. Clone the repository and install it
in editable mode if you want to use it as a dependency:

```bash
git clone <repository-url>
cd complexity_analyzer
pip install -e .
```

Alternatively, run the module directly without installation by pointing
`PYTHONPATH` at the project root.

## Command Line Usage

```bash
# Auto-detect the language from the file extension
python -m complexity_analyzer path/to/file.py

# Analyze a Java source file explicitly
python -m complexity_analyzer --language java path/to/Foo.java

# Emit JSON instead of the text report
python -m complexity_analyzer --format json path/to/file.py

# Include the Halstead operator/operand maps in the JSON payload
python -m complexity_analyzer --format json --show-operands path/to/file.java
```

The command exits with a non-zero status if the file cannot be located or the
language cannot be detected from the extension.

## Library Usage

You can import the core helpers to integrate the analyzer into your own tools:

```python
from complexity_analyzer import analyze_file, available_languages

print(available_languages())  # ['java', 'javascript', 'python', 'typescript']
metrics = analyze_file("src/example/Foo.java")
```

Each call returns a dictionary containing the metrics listed above. When using
JSON output from the CLI, the Halstead operator/operand frequency tables are
omitted by default to keep the payload concise. Pass `--show-operands` to retain
the detailed maps.

## Language Support

### Python

Python files benefit from detailed metrics, including per-function cyclomatic
complexity driven by the built-in AST module.

### Java

Java files use lexical tokenization to compute Halstead and cyclomatic
complexity scores, while the maintainability index is derived from those metrics
and the effective source lines of code. Per-method cyclomatic complexity is not
currently reported for Java because it would require a full parser, but the
aggregate results match the module-level reporting used by many tools.

### JavaScript

JavaScript analysis mirrors the Java approach. The analyzer recognizes modern
syntax, strips comments, and performs token-based Halstead and cyclomatic
complexity calculations across `.js`, `.jsx`, `.mjs`, and `.cjs` files.

### TypeScript

TypeScript analysis reuses the JavaScript pipeline so you can inspect metrics
for `.ts`, `.tsx`, `.cts`, `.mts`, and declaration files without additional
configuration.

## Development

Run the unit test suite with:

```bash
pytest -q
```

Contributions that expand language support or improve the accuracy of the
metrics are welcome.
