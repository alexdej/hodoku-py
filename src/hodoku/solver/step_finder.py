"""SudokuStepFinder — central dispatcher for all technique solvers.

Mirrors Java's SudokuStepFinder. Currently only SimpleSolver is wired in;
additional solvers will be added as they are implemented.
"""

from __future__ import annotations

from hodoku.core.grid import Grid
from hodoku.core.solution_step import SolutionStep
from hodoku.core.types import SolutionType
from hodoku.solver.als import AlsSolver
from hodoku.solver.brute_force import BruteForceSolver
from hodoku.solver.chains import ChainSolver
from hodoku.solver.coloring import ColoringSolver
from hodoku.solver.fish import FishSolver
from hodoku.solver.simple import SimpleSolver
from hodoku.solver.single_digit import SingleDigitSolver
from hodoku.solver.uniqueness import UniquenessSolver
from hodoku.solver.wings import WingSolver


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
    SolutionType.FINNED_X_WING,
    SolutionType.FINNED_SWORDFISH,
    SolutionType.FINNED_JELLYFISH,
    SolutionType.SASHIMI_X_WING,
    SolutionType.SASHIMI_SWORDFISH,
    SolutionType.SASHIMI_JELLYFISH,
})

_ALS_TYPES = frozenset({
    SolutionType.ALS_XZ,
    SolutionType.ALS_XY_WING,
    SolutionType.ALS_XY_CHAIN,
    SolutionType.DEATH_BLOSSOM,
})

_CHAIN_TYPES = frozenset({
    SolutionType.TURBOT_FISH,
    SolutionType.X_CHAIN,
    SolutionType.XY_CHAIN,
    SolutionType.REMOTE_PAIR,
    SolutionType.CONTINUOUS_NICE_LOOP,          # trigger for all NL types (DNL + CNL)
    SolutionType.DISCONTINUOUS_NICE_LOOP,        # aliased to same score; dispatched here too
    SolutionType.GROUPED_CONTINUOUS_NICE_LOOP,   # trigger for all GNL types
    SolutionType.GROUPED_DISCONTINUOUS_NICE_LOOP,
    SolutionType.GROUPED_AIC,
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
        self._chains = ChainSolver(grid)
        self._als = AlsSolver(grid)
        self._brute_force = BruteForceSolver(grid)

    def find_all(self, sol_type: SolutionType) -> list[SolutionStep]:
        """Return ALL steps of the given type (for /bsa mode and reglib harness).

        Solvers that implement find_all() natively return every instance.
        All others fall back to get_step() and return 0 or 1 result.
        """
        if sol_type in _SIMPLE_TYPES:
            return self._simple.find_all(sol_type)
        step = self.get_step(sol_type)
        return [step] if step is not None else []

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
        if sol_type in _ALS_TYPES:
            return self._als.get_step(sol_type)
        if sol_type in _CHAIN_TYPES:
            return self._chains.get_step(sol_type)
        if sol_type is SolutionType.BRUTE_FORCE:
            return self._brute_force.get_step(sol_type)
        return None
