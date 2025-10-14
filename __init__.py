"""
Complexity Analyzer

Lightweight static analysis for Python files: LOC, Cyclomatic
Complexity, Halstead metrics, and Maintainability Index.

Usage (CLI):
  python -m complexity_analyzer path/to/file.py
  python -m complexity_analyzer --format json path/to/file.py
"""

__all__ = [
    "analyze_file",
]

from .core import analyze_file  # re-export for convenience

