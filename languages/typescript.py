from __future__ import annotations

from pathlib import Path
from typing import Dict

from .javascript import JavaScriptAnalyzer


class TypeScriptAnalyzer(JavaScriptAnalyzer):
    """Complexity analyzer for TypeScript sources.

    The implementation reuses the JavaScript analyzer because the two languages
    share the same lexical structure for complexity metrics. TypeScript extends
    JavaScript with type annotations and a handful of additional keywords, but
    those constructs do not affect the token-based Halstead and cyclomatic
    calculations performed by the parent class.
    """

    language = "typescript"
    extensions = {".ts", ".tsx", ".cts", ".mts", ".d.ts"}

    def supports(self, path: Path) -> bool:
        # Handle multi-part extensions such as ".d.ts" in addition to the simple
        # suffix handling provided by the base implementation.
        name = path.name.lower()
        return any(name.endswith(ext) for ext in self.extensions)

    def analyze(self, path: Path) -> Dict:
        return super().analyze(path)
