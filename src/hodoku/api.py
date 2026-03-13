"""Public API — the only import most users need."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from hodoku.core.grid import ALL_UNITS, Grid
from hodoku.core.scoring import SOLVER_STEPS
from hodoku.core.solution_step import SolutionStep
from hodoku.core.types import DifficultyType
from hodoku.solver.solver import SudokuSolver
from hodoku.solver.step_finder import SudokuStepFinder

_VALID_CELL_CHARS = frozenset("0123456789.")


def _validate_puzzle(puzzle: str) -> None:
    """Raise ValueError for malformed puzzle strings.

    Accepts the same format as Grid.set_sudoku: 81 characters, each '0'-'9'
    or '.'.  Also accepts the '+D' placed-cell prefix notation.  Raises on
    invalid characters, wrong cell count, or duplicate digits in any house.
    """
    cells: list[str] = []
    i = 0
    while i < len(puzzle):
        ch = puzzle[i]
        if ch == "+":
            i += 1
            if i < len(puzzle):
                ch = puzzle[i]
                if ch not in _VALID_CELL_CHARS:
                    raise ValueError(f"Invalid character after '+': {ch!r}")
                cells.append(ch)
        elif ch in _VALID_CELL_CHARS:
            cells.append(ch)
        else:
            raise ValueError(f"Invalid character in puzzle string: {ch!r}")
        i += 1

    if len(cells) != 81:
        raise ValueError(f"Puzzle must have exactly 81 cells, got {len(cells)}")

    # Check for duplicate digits within each house (row, col, box)
    for unit in ALL_UNITS:
        seen: dict[str, int] = {}
        for idx in unit:
            d = cells[idx]
            if d in ("0", "."):
                continue
            if d in seen:
                raise ValueError(
                    f"Duplicate digit {d} in house (cells {seen[d]} and {idx})"
                )
            seen[d] = idx


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
        _validate_puzzle(puzzle)
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
        _validate_puzzle(puzzle)
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
        _validate_puzzle(puzzle)
        result = self._solver.solve(puzzle)
        return RatingResult(level=result.level, score=result.score)

    def find_all_steps(self, puzzle: str) -> list[SolutionStep]:
        """Return every applicable technique at the current grid state."""
        _validate_puzzle(puzzle)
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
