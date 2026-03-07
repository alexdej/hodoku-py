"""Public API — the only import most users need."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from hodoku.core.solution_step import SolutionStep
from hodoku.core.types import DifficultyType, SolutionType


@dataclass
class SolveResult:
    solved: bool
    steps: list[SolutionStep]
    level: DifficultyType
    score: int
    solution: str  # 81-char string


@dataclass
class RatingResult:
    level: DifficultyType
    score: int


class Solver:
    """Solves and analyses sudoku puzzles using human-style logic."""

    def solve(self, puzzle: str) -> SolveResult:
        """Solve a puzzle string, returning the full solution path."""
        raise NotImplementedError

    def get_hint(self, puzzle: str) -> SolutionStep | None:
        """Return the next logical step, or None if already solved."""
        raise NotImplementedError

    def rate(self, puzzle: str) -> RatingResult:
        """Return difficulty level and score without recording solution steps."""
        raise NotImplementedError

    def find_all_steps(self, puzzle: str) -> list[SolutionStep]:
        """Return every applicable technique at the current grid state."""
        raise NotImplementedError


class Generator:
    """Generates valid sudoku puzzles."""

    def generate(
        self,
        difficulty: DifficultyType = DifficultyType.MEDIUM,
        pattern: list[int] | None = None,
    ) -> str:
        """Generate an 81-character puzzle string at the requested difficulty."""
        raise NotImplementedError

    def validate(self, puzzle: str) -> Literal["valid", "invalid", "multiple"]:
        """Check whether a puzzle has exactly one solution."""
        raise NotImplementedError
