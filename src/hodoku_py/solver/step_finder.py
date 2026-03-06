"""SudokuStepFinder — central dispatcher for all technique solvers.

Mirrors Java's SudokuStepFinder. Currently only SimpleSolver is wired in;
additional solvers will be added as they are implemented.
"""

from __future__ import annotations

from hodoku_py.core.grid import Grid
from hodoku_py.core.solution_step import SolutionStep
from hodoku_py.core.types import SolutionType
from hodoku_py.solver.coloring import ColoringSolver
from hodoku_py.solver.fish import FishSolver
from hodoku_py.solver.simple import SimpleSolver
from hodoku_py.solver.single_digit import SingleDigitSolver
from hodoku_py.solver.uniqueness import UniquenessSolver
from hodoku_py.solver.wings import WingSolver


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

_SINGLE_DIGIT_TYPES = frozenset({
    SolutionType.SKYSCRAPER,
    SolutionType.TWO_STRING_KITE,
    SolutionType.EMPTY_RECTANGLE,
})

_WING_TYPES = frozenset({
    SolutionType.W_WING,
    SolutionType.XY_WING,
    SolutionType.XYZ_WING,
})

_COLORING_TYPES = frozenset({
    SolutionType.SIMPLE_COLORS_TRAP,
    SolutionType.SIMPLE_COLORS_WRAP,
    SolutionType.MULTI_COLORS_1,
    SolutionType.MULTI_COLORS_2,
})

_FISH_TYPES = frozenset({
    SolutionType.X_WING,
    SolutionType.SWORDFISH,
    SolutionType.JELLYFISH,
})

_UNIQUENESS_TYPES = frozenset({
    SolutionType.UNIQUENESS_1,
    SolutionType.UNIQUENESS_2,
    SolutionType.UNIQUENESS_3,
    SolutionType.UNIQUENESS_4,
    SolutionType.UNIQUENESS_5,
    SolutionType.UNIQUENESS_6,
    SolutionType.HIDDEN_RECTANGLE,
    SolutionType.BUG_PLUS_1,
})


class SudokuStepFinder:
    """Dispatches get_step() calls to the appropriate specialized solver."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid
        self._simple = SimpleSolver(grid)
        self._single_digit = SingleDigitSolver(grid)
        self._wings = WingSolver(grid)
        self._coloring = ColoringSolver(grid)
        self._fish = FishSolver(grid)
        self._uniqueness = UniquenessSolver(grid)

    def get_step(self, sol_type: SolutionType) -> SolutionStep | None:
        """Return the next step of the given type, or None if not found."""
        if sol_type in _SIMPLE_TYPES:
            return self._simple.get_step(sol_type)
        if sol_type in _SINGLE_DIGIT_TYPES:
            return self._single_digit.get_step(sol_type)
        if sol_type in _WING_TYPES:
            return self._wings.get_step(sol_type)
        if sol_type in _COLORING_TYPES:
            return self._coloring.get_step(sol_type)
        if sol_type in _FISH_TYPES:
            return self._fish.get_step(sol_type)
        if sol_type in _UNIQUENESS_TYPES:
            return self._uniqueness.get_step(sol_type)
        return None
