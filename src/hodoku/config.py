"""SolverConfig — unified configuration for the solver and find-all-steps paths.

Replaces scattered module-level constants with a single config object that can
be passed to Solver().  Default values reproduce the current hardcoded behaviour
exactly, so ``SolverConfig()`` is a drop-in replacement.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING

from hodoku.core.types import DifficultyType, SolutionType

if TYPE_CHECKING:
    from hodoku.core.scoring import StepConfig


# ---------------------------------------------------------------------------
# FishType enum
# ---------------------------------------------------------------------------

class FishType(enum.IntEnum):
    BASIC = 0
    BASIC_FRANKEN = 1
    BASIC_FRANKEN_MUTANT = 2


# ---------------------------------------------------------------------------
# Fish search configs
# ---------------------------------------------------------------------------

ALL_CANDIDATES: int = 0x1FF  # bits 0-8 set = digits 1-9


def make_candidates(digits: list[int]) -> int:
    """Build a 9-bit candidate mask from a list of digits 1-9."""
    return sum(1 << (d - 1) for d in digits)


@dataclass(frozen=True)
class FishSearchConfig:
    search_fish: bool = True
    fish_type: FishType = FishType.BASIC_FRANKEN
    min_size: int = 2
    max_size: int = 4
    max_fins: int = 5
    max_endo_fins: int = 2
    check_templates: bool = True
    only_one_per_elimination: bool = True
    candidates: int = ALL_CANDIDATES


@dataclass(frozen=True)
class KrakenFishSearchConfig:
    search_kraken_fish: bool = False
    fish_type: FishType = FishType.BASIC_FRANKEN
    min_size: int = 2
    max_size: int = 4
    max_fins: int = 2
    max_endo_fins: int = 0
    candidates: int = ALL_CANDIDATES


# ---------------------------------------------------------------------------
# StepSearchConfig
# ---------------------------------------------------------------------------

# Default disabled types for find-all (last-resort techniques unchecked in HoDoKu UI)
_FIND_ALL_DISABLED: frozenset[SolutionType] = frozenset({
    SolutionType.KRAKEN_FISH_TYPE_1,
    SolutionType.KRAKEN_FISH_TYPE_2,
    SolutionType.FORCING_CHAIN_CONTRADICTION,
    SolutionType.FORCING_CHAIN_VERITY,
    SolutionType.FORCING_NET_CONTRADICTION,
    SolutionType.FORCING_NET_VERITY,
    SolutionType.TEMPLATE_SET,
    SolutionType.TEMPLATE_DEL,
})


@dataclass(frozen=True)
class StepSearchConfig:
    fish: FishSearchConfig = field(default_factory=FishSearchConfig)
    kraken_fish: KrakenFishSearchConfig = field(default_factory=KrakenFishSearchConfig)
    chain_max_length: int = 20
    nice_loop_max_length: int = 10
    chain_restrict_length: bool = True
    tabling_entry_size: int = 1000
    tabling_net_depth: int = 4
    tabling_only_one_chain_per_elimination: bool = True
    tabling_allow_als_in_chains: bool = False
    als_allow_overlap: bool = False
    als_only_one_per_elimination: bool = True
    als_chain_length: int = 6
    als_chain_forward_only: bool = True
    allow_ers_with_two_candidates: bool = False
    allow_duals_and_siamese: bool = False
    allow_missing_candidates_in_urs: bool = False
    disabled_types: frozenset[SolutionType] = frozenset()


def _default_solve_search() -> StepSearchConfig:
    """Solve-path defaults — matches current hardcoded behaviour."""
    return StepSearchConfig()


def _default_find_all_search() -> StepSearchConfig:
    """Find-all-steps defaults — more permissive than solve."""
    return StepSearchConfig(
        tabling_allow_als_in_chains=True,
        tabling_only_one_chain_per_elimination=False,
        als_allow_overlap=True,
        als_only_one_per_elimination=False,
        disabled_types=_FIND_ALL_DISABLED,
    )


# ---------------------------------------------------------------------------
# SolverConfig
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SolverConfig:
    solve_search: StepSearchConfig = field(default_factory=_default_solve_search)
    find_all_search: StepSearchConfig = field(default_factory=_default_find_all_search)
    step_overrides: dict[SolutionType, dict] = field(default_factory=dict)
    difficulty_thresholds: dict[DifficultyType, int] = field(default_factory=dict)

    @cached_property
    def solver_steps(self) -> tuple[StepConfig, ...]:
        """Enabled steps sorted by index — mirrors module-level SOLVER_STEPS."""
        from hodoku.core.scoring import DEFAULT_STEPS, StepConfig as SC

        if not self.step_overrides:
            from hodoku.core.scoring import SOLVER_STEPS
            return SOLVER_STEPS

        steps: list[SC] = []
        for s in DEFAULT_STEPS:
            overrides = self.step_overrides.get(s.solution_type)
            if overrides:
                vals = {f: getattr(s, f) for f in s.__dataclass_fields__}
                vals.update(overrides)
                s = SC(**vals)
            steps.append(s)
        return tuple(sorted((s for s in steps if s.enabled), key=lambda s: s.index))

    @cached_property
    def all_steps(self) -> tuple[StepConfig, ...]:
        """All steps sorted by index (for find-all iteration)."""
        from hodoku.core.scoring import DEFAULT_STEPS, StepConfig as SC

        if not self.step_overrides:
            return tuple(sorted(DEFAULT_STEPS, key=lambda s: s.index))

        steps: list[SC] = []
        for s in DEFAULT_STEPS:
            overrides = self.step_overrides.get(s.solution_type)
            if overrides:
                vals = {f: getattr(s, f) for f in s.__dataclass_fields__}
                vals.update(overrides)
                s = SC(**vals)
            steps.append(s)
        return tuple(sorted(steps, key=lambda s: s.index))

    @cached_property
    def step_config(self) -> dict[SolutionType, StepConfig]:
        """Fast lookup by SolutionType, including aliases."""
        from hodoku.core.scoring import STEP_CONFIG as _BASE

        if not self.step_overrides:
            return dict(_BASE)

        from hodoku.core.scoring import DEFAULT_STEPS, StepConfig as SC

        result: dict[SolutionType, SC] = {}
        for s in DEFAULT_STEPS:
            overrides = self.step_overrides.get(s.solution_type)
            if overrides:
                vals = {f: getattr(s, f) for f in s.__dataclass_fields__}
                vals.update(overrides)
                s = SC(**vals)
            result[s.solution_type] = s

        # Aliases (same as scoring.py)
        _S = SolutionType
        result[_S.SIMPLE_COLORS_WRAP] = result[_S.SIMPLE_COLORS_TRAP]
        result[_S.MULTI_COLORS_2] = result[_S.MULTI_COLORS_1]
        result[_S.DISCONTINUOUS_NICE_LOOP] = result[_S.CONTINUOUS_NICE_LOOP]
        result[_S.AIC] = result[_S.CONTINUOUS_NICE_LOOP]
        result[_S.GROUPED_DISCONTINUOUS_NICE_LOOP] = result[_S.GROUPED_CONTINUOUS_NICE_LOOP]
        result[_S.GROUPED_AIC] = result[_S.GROUPED_CONTINUOUS_NICE_LOOP]
        result[_S.FORCING_CHAIN_VERITY] = result[_S.FORCING_CHAIN_CONTRADICTION]
        result[_S.FORCING_NET_VERITY] = result[_S.FORCING_NET_CONTRADICTION]
        result[_S.KRAKEN_FISH_TYPE_2] = result[_S.KRAKEN_FISH_TYPE_1]
        result[_S.DUAL_TWO_STRING_KITE] = result[_S.TWO_STRING_KITE]
        result[_S.DUAL_EMPTY_RECTANGLE] = result[_S.EMPTY_RECTANGLE]
        return result

    @cached_property
    def _difficulty_max_score(self) -> dict[DifficultyType, int]:
        """Difficulty thresholds with overrides applied."""
        from hodoku.core.scoring import DIFFICULTY_MAX_SCORE
        if not self.difficulty_thresholds:
            return dict(DIFFICULTY_MAX_SCORE)
        result = dict(DIFFICULTY_MAX_SCORE)
        result.update(self.difficulty_thresholds)
        return result


# Module-level default instance — shared across Solver(), SudokuSolver(),
# Generator() when no config is provided.  Frozen + cached_property means
# derived tables (solver_steps, step_config) are computed once.
DEFAULT_CONFIG = SolverConfig()
