"""
Complexity Analyzer

Lightweight static analysis for supported languages (Python, Java, JavaScript):
LOC, Cyclomatic Complexity, Halstead metrics, and Maintainability Index.

Usage (CLI):
  python -m complexity_analyzer path/to/file.py
  python -m complexity_analyzer --language java path/to/File.java
  python -m complexity_analyzer --format json path/to/file.py
"""

__all__ = [
    "analyze_file",
    "format_text_report",
    "available_languages",
    "detect_language",
]

from .core import analyze_file, available_languages, detect_language, format_text_report  # re-export for convenience
