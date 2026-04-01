"""SudokuSolver — main solve loop with scoring and difficulty rating.

Mirrors Java's SudokuSolver.solve(). Iterates SOLVER_STEPS in priority order,
tries each enabled technique in turn, applies the first step found, and repeats
until the puzzle is solved or no progress can be made.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hodoku.core.grid import Grid
from hodoku.core.solution_step import SolutionStep
from hodoku.core.types import DifficultyType, SolutionType
from hodoku.solver.step_finder import SudokuStepFinder

if TYPE_CHECKING:
    from hodoku.config import SolverConfig


@dataclass
class SolveResult:
    """Result of a solve() call."""
    puzzle: str
    steps: list[SolutionStep] = field(default_factory=list)
    level: DifficultyType = DifficultyType.INCOMPLETE
    score: int = 0
    solved: bool = False
    solution: str = ""  # 81-char grid after all steps applied


_PLACEMENT_TYPES: frozenset[SolutionType] = frozenset({
    SolutionType.FULL_HOUSE,
    SolutionType.NAKED_SINGLE,
    SolutionType.HIDDEN_SINGLE,
    SolutionType.BRUTE_FORCE,
    # Forcing chains/nets can set values via contradiction/verity
    SolutionType.FORCING_CHAIN_CONTRADICTION,
    SolutionType.FORCING_CHAIN_VERITY,
    SolutionType.FORCING_NET_CONTRADICTION,
    SolutionType.FORCING_NET_VERITY,
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

    def __init__(self, config: SolverConfig | None = None) -> None:
        if config is None:
            from hodoku.config import SolverConfig as _SC
            config = _SC()
        self._config = config

    def solve(self, puzzle: str) -> SolveResult:
        """Solve *puzzle* and return a SolveResult with steps, level, and score."""
        grid = Grid()
        grid.set_sudoku(puzzle)

        result = SolveResult(puzzle=grid.get_sudoku_string())
        finder = SudokuStepFinder(grid, self._config.solve_search)

        step_config = self._config.step_config
        difficulty_max = self._config._difficulty_max_score
        solver_steps = self._config.solver_steps

        max_level = DifficultyType.INCOMPLETE
        total_score = 0

        while not grid.is_solved():
            step = self._find_next_step(finder, solver_steps)
            if step is None:
                # No technique could make progress
                break
            _apply_step(grid, step)
            result.steps.append(step)

            cfg = step_config.get(step.type)
            if cfg is not None:
                total_score += cfg.base_score
                if cfg.level.value > max_level.value:
                    max_level = cfg.level

        result.solved = grid.is_solved()
        result.score = total_score
        if result.solved:
            # Mirror Java's post-solve score-threshold bump:
            # while (score > level.getMaxScore()) level = nextLevel
            level = max_level
            while difficulty_max.get(level, 2**31 - 1) < total_score:
                level = DifficultyType(level.value + 1)
            result.level = level
        else:
            result.level = DifficultyType.INCOMPLETE
        result.solution = grid.get_sudoku_string()
        return result

    @staticmethod
    def _find_next_step(finder: SudokuStepFinder, solver_steps) -> SolutionStep | None:
        """Try each enabled technique in priority order; return first hit."""
        for cfg in solver_steps:
            step = finder.get_step(cfg.solution_type)
            if step is not None:
                return step
        return None
