# Complexity Analyzer – Agents Guide

## Mission & Success Criteria
- Compute deterministic LOC, cyclomatic complexity, Halstead metrics, and Maintainability Index for Python, Java, JavaScript, and TypeScript source files via the CLI (`python -m complexity_analyzer`) or library helpers (`analyze_file`, `format_text_report`).
- Success means: metrics remain accurate for existing languages, CLI/JSON output formats stay backward compatible, and new functionality ships with tests.

## When to Engage an Agent
- Adding or enhancing a language analyzer (new tokens, keyword sets, LOC handling, multi-extension detection).
- Improving reporting/formatting or CLI ergonomics.
- Diagnosing inaccuracies in the computed metrics or performance regressions.
- Keeping docs/tests in sync with new metrics or options.

## Architecture Cheat Sheet
- `core.py`:
  - `_build_analyzers` registers `PythonAnalyzer`, `JavaAnalyzer`, `JavaScriptAnalyzer`, `TypeScriptAnalyzer`; extend this when adding languages.
  - `detect_language` + `_get_analyzer` drive extension-based routing; keep the error messages descriptive.
  - `analyze_file` is the library entrypoint; raise `FileNotFoundError`/`ValueError` on invalid inputs.
  - `format_text_report` is the canonical CLI formatting logic.
- `__main__.py`: CLI that wires argparse → `analyze_file`, supports `--format`, `--language`, `--show-operands`, and returns exit codes 0/2/3.
- `languages/`: Each analyzer subclasses `BaseAnalyzer` and returns a metrics dict with `summary`, `cyclomatic`, `halstead`, `maintainability_index`, and `warnings`. Python uses AST parsing and per-function complexities; Java/JavaScript tokenize and count keywords/operators; TypeScript inherits from JavaScript but overrides extension detection for `.d.ts`.
- `tests/test_core.py`: Integration-style tests covering language detection, per-language metrics invariants, CLI JSON/text behavior, and error codes.

## Implementation Guardrails
- Keep the package dependency-free; rely only on the standard library unless the request explicitly justifies more.
- Preserve analyzer determinism: tokenizers must ignore comments/docstrings consistently; AST parsing must gracefully degrade (Python analyzer emits warnings on `SyntaxError`).
- Maintain the metrics payload shape. When adding fields, update both `format_text_report` and JSON serialization, plus fixtures/tests.
- Register new analyzers by updating `_build_analyzers` and, if needed, `_EXTENSION_MAP` initialization logic to cover new suffixes.
- Operations should remain file-scoped; avoid multi-file traversal or project-wide state.
- Follow the Warning pattern: prefer accumulating human-readable warnings rather than throwing when a single file has recoverable issues.
- Documentation and tests must describe any observable change (new CLI flag, metric, analyzer support).

## Feature & Language Heuristics
- **Python**: Use `ast` for cyclomatic complexity and docstring detection. Tokenization (`tokenize`) drives LOC and Halstead counts. Ensure visitors handle async defs, pattern matching, and comprehensions. Syntax errors should keep LOC counts accurate, set cyclomatic to 1, and add a warning.
- **Java**: Strip block/line comments before tokenization. Update keyword/operator sets when Java releases new syntax. Cyclomatic counts trigger on `DECISION_KEYWORDS`; keep operator parsing in sync with `MULTI_CHAR_OPERATORS`.
- **JavaScript/TypeScript**: Lexer must distinguish regex literals from division, spread vs. rest, and nullish-coalescing operators. TypeScript analyzer only overrides extensions and inherits JS behavior—avoid introducing TS-only logic unless unavoidable, then consider whether JS should also gain it.
- **New languages**: Derive from `BaseAnalyzer`, expose `language`, `extensions`, and implement `analyze` returning the standard metrics dict. Provide fixtures/tests demonstrating LOC, cyclomatic, Halstead, and MI boundaries.

## Testing & Verification
- Default regression suite: `pytest -q`.
- Targeted tests:
  - When touching CLI behavior, add/adjust cases in `tests/test_core.py` (e.g., new arguments, error codes, JSON structure).
  - For analyzer changes, craft fixtures under `tmp_path` inside the existing parametrized tests or add new ones to cover edge cases (comments, async/await, template strings, etc.).
- Manual spot checks:
  - `python -m complexity_analyzer path/to/file.py`
  - `python -m complexity_analyzer --format json --show-operands tests/samples/foo.java`
  - Compare before/after reports for representative files to ensure no unexpected drift.
- Ensure `--format json` output omits the operators/operands maps unless `--show-operands` is passed.

## Agent Workflow
1. Clarify the goal and whether it touches CLI, analyzers, or documentation.
2. Identify the files involved (see Architecture Cheat Sheet) and outline the minimal surface area to change.
3. Implement changes with incremental tests (or expand fixtures) so failures pinpoint regressions.
4. Run `pytest -q`; rerun targeted snippets or CLI commands if the change affects runtime behavior.
5. Update README/agents.md/examples to reflect new behavior, then summarize the change and verification evidence.

## Delivery Checklist
- Code changes complete, formatted, and linted (no repo-specific linter exists, so rely on Python’s defaults).
- Relevant tests added/updated and `pytest -q` passes locally.
- CLI/manual checks captured (command + expected behavior).
- Docs updated (README, this guide, or inline docstrings).
- Note any follow-up work or observed debt in the PR/summary.

## Quick Reference Commands
```bash
# Run the unit tests
pytest -q

# Analyze a file with text output (auto-detect language)
python -m complexity_analyzer path/to/file.py

# Analyze explicitly with JSON output and show Halstead operand/operator maps
python -m complexity_analyzer --language javascript --format json --show-operands path/to/file.js
```
