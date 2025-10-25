from __future__ import annotations

import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Iterable


class BaseAnalyzer(ABC):
    """Abstract interface for language-specific complexity analyzers."""

    #: Lowercased file extensions supported by this analyzer (including leading dot).
    extensions: Iterable[str] = ()
    #: Identifier for the language (e.g., "python", "java").
    language: str = "unknown"

    def supports(self, path: Path) -> bool:
        return path.suffix.lower() in set(ext.lower() for ext in self.extensions)

    @abstractmethod
    def analyze(self, path: Path) -> Dict:
        """Return the metrics for the given file."""
        raise NotImplementedError


def maintainability_index(volume: float, cyclomatic: int, sloc: int) -> float:
    """
    Compute the SEI/Visual Studio scaled maintainability index without comment weight.
    """
    if volume <= 0 or sloc <= 0:
        return 100.0
    try:
        score = 171.0 - 5.2 * math.log(volume) - 0.23 * float(cyclomatic) - 16.2 * math.log(sloc)
    except (ValueError, OverflowError):
        return 0.0
    return max(0.0, min(100.0, (score * 100.0) / 171.0))
