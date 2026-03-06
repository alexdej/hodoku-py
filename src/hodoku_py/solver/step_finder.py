"""SudokuStepFinder — central dispatcher for all technique solvers.

Mirrors Java's SudokuStepFinder. Currently only SimpleSolver is wired in;
additional solvers will be added as they are implemented.
"""

from __future__ import annotations

from hodoku_py.core.grid import Grid
from hodoku_py.core.solution_step import SolutionStep
from hodoku_py.core.types import SolutionType
from hodoku_py.solver.simple import SimpleSolver


_SIMPLE_TYPES = frozenset({
    SolutionType.FULL_HOUSE,
    SolutionType.NAKED_SINGLE,
    SolutionType.HIDDEN_SINGLE,
    SolutionType.LOCKED_CANDIDATES_1,
    SolutionType.LOCKED_CANDIDATES_2,
    SolutionType.LOCKED_PAIR,
    SolutionType.NAKED_PAIR,
    SolutionType.LOCKED_TRIPLE,
    SolutionType.NAKED_TRIPLE,
    SolutionType.NAKED_QUADRUPLE,
    SolutionType.HIDDEN_PAIR,
    SolutionType.HIDDEN_TRIPLE,
    SolutionType.HIDDEN_QUADRUPLE,
})


class SudokuStepFinder:
    """Dispatches get_step() calls to the appropriate specialized solver."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid
        self._simple = SimpleSolver(grid)

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        """Return the next step of the given type, or None if not found."""
        if sol_type in _SIMPLE_TYPES:
            return self._simple.get_step(sol_type)
        return None
