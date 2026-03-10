"""Public API — the only import most users need."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from hodoku.core.grid import Grid
from hodoku.core.scoring import SOLVER_STEPS, STEP_CONFIG
from hodoku.core.solution_step import SolutionStep
from hodoku.core.types import DifficultyType, SolutionType
from hodoku.solver.solver import SudokuSolver
from hodoku.solver.step_finder import SudokuStepFinder


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

    def __init__(self) -> None:
        self._solver = SudokuSolver()

    def solve(self, puzzle: str) -> SolveResult:
        """Solve a puzzle string, returning the full solution path."""
        result = self._solver.solve(puzzle)
        return SolveResult(
            solved=result.solved,
            steps=result.steps,
            level=result.level,
            score=result.score,
            solution=result.solution,
        )

    def get_hint(self, puzzle: str) -> SolutionStep | None:
        """Return the next logical step, or None if already solved or stuck."""
        grid = Grid()
        grid.set_sudoku(puzzle)
        if grid.is_solved():
            return None
        finder = SudokuStepFinder(grid)
        for cfg in SOLVER_STEPS:
            step = finder.get_step(cfg.solution_type)
            if step is not None:
                return step
        return None

    def rate(self, puzzle: str) -> RatingResult:
        """Return difficulty level and score without recording solution steps."""
        result = self._solver.solve(puzzle)
        return RatingResult(level=result.level, score=result.score)

    def find_all_steps(self, puzzle: str) -> list[SolutionStep]:
        """Return every applicable technique at the current grid state."""
        grid = Grid()
        grid.set_sudoku(puzzle)
        finder = SudokuStepFinder(grid)
        steps: list[SolutionStep] = []
        for cfg in SOLVER_STEPS:
            if cfg.all_steps_enabled:
                steps.extend(finder.find_all(cfg.solution_type))
        return steps


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
