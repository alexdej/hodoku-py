"""SudokuSolver — main solve loop with scoring and difficulty rating.

Mirrors Java's SudokuSolver.solve(). Iterates SOLVER_STEPS in priority order,
tries each enabled technique in turn, applies the first step found, and repeats
until the puzzle is solved or no progress can be made.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hodoku_py.core.grid import Grid
from hodoku_py.core.scoring import SOLVER_STEPS, STEP_CONFIG
from hodoku_py.core.solution_step import SolutionStep
from hodoku_py.core.types import DifficultyType, SolutionType
from hodoku_py.solver.step_finder import SudokuStepFinder


@dataclass
class SolveResult:
    """Result of a solve() call."""
    puzzle: str
    steps: list[SolutionStep] = field(default_factory=list)
    level: DifficultyType = DifficultyType.INCOMPLETE
    score: int = 0
    solved: bool = False


_PLACEMENT_TYPES: frozenset[SolutionType] = frozenset({
    SolutionType.FULL_HOUSE,
    SolutionType.NAKED_SINGLE,
    SolutionType.HIDDEN_SINGLE,
})


def _apply_step(grid: Grid, step: SolutionStep) -> None:
    """Apply a solution step to the grid.

    For placement steps (singles), set_cell is called for each (index, value).
    For elimination steps (LC, subsets, …), only candidates_to_delete is applied.
    In both cases, step.indices on non-placement steps is pattern context only.
    """
    if step.type in _PLACEMENT_TYPES:
        for idx, val in zip(step.indices, step.values):
            grid.set_cell(idx, val)
    for cand in step.candidates_to_delete:
        grid.del_candidate(cand.index, cand.value)


class SudokuSolver:
    """Iterative solver that mirrors the HoDoKu solve loop."""

    def solve(self, puzzle: str) -> SolveResult:
        """Solve *puzzle* and return a SolveResult with steps, level, and score."""
        grid = Grid()
        grid.set_sudoku(puzzle)

        result = SolveResult(puzzle=grid.get_sudoku_string())
        finder = SudokuStepFinder(grid)

        max_level = DifficultyType.INCOMPLETE
        total_score = 0

        while not grid.is_solved():
            step = self._find_next_step(finder)
            if step is None:
                # No technique could make progress
                break
            _apply_step(grid, step)
            result.steps.append(step)

            cfg = STEP_CONFIG.get(step.type)
            if cfg is not None:
                total_score += cfg.base_score
                if cfg.level.value > max_level.value:
                    max_level = cfg.level

        result.solved = grid.is_solved()
        result.score = total_score
        result.level = max_level if result.solved else DifficultyType.INCOMPLETE
        return result

    def _find_next_step(self, finder: SudokuStepFinder) -> SolutionStep | None:
        """Try each enabled technique in priority order; return first hit."""
        for cfg in SOLVER_STEPS:
            step = finder.get_step(cfg.solution_type)
            if step is not None:
                return step
        return None
