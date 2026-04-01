"""Unit tests for SolverConfig and related config classes."""

from __future__ import annotations

import pytest

from hodoku.config import (
    DEFAULT_CONFIG,
    FishSearchConfig,
    FishType,
    KrakenFishSearchConfig,
    SolverConfig,
    StepSearchConfig,
    make_candidates,
    _default_find_all_search,
    _default_solve_search,
)
from hodoku.core.scoring import DIFFICULTY_MAX_SCORE, SOLVER_STEPS, STEP_CONFIG
from hodoku.core.types import DifficultyType, SolutionType

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# make_candidates
# ---------------------------------------------------------------------------

class TestMakeCandidates:
    def test_single_digit(self):
        assert make_candidates([1]) == 0b1

    def test_multiple_digits(self):
        assert make_candidates([1, 2, 3]) == 0b111

    def test_all_digits(self):
        assert make_candidates(list(range(1, 10))) == 0x1FF

    def test_empty(self):
        assert make_candidates([]) == 0


# ---------------------------------------------------------------------------
# Default config matches hardcoded tables
# ---------------------------------------------------------------------------

class TestDefaultConfig:
    def test_solver_steps_matches_module(self):
        assert DEFAULT_CONFIG.solver_steps == SOLVER_STEPS

    def test_step_config_matches_module(self):
        assert DEFAULT_CONFIG.step_config == STEP_CONFIG

    def test_difficulty_thresholds_matches_module(self):
        assert DEFAULT_CONFIG._difficulty_max_score == DIFFICULTY_MAX_SCORE

    def test_singleton_identity(self):
        from hodoku import Solver
        s1 = Solver()
        s2 = Solver()
        assert s1._config is s2._config
        assert s1._config is DEFAULT_CONFIG

    def test_all_steps_includes_disabled(self):
        """all_steps includes entries with enabled=False (e.g. SQUIRMBAG)."""
        types = {s.solution_type for s in DEFAULT_CONFIG.all_steps}
        assert SolutionType.SQUIRMBAG in types

    def test_solver_steps_excludes_disabled(self):
        """solver_steps only includes enabled=True entries."""
        types = {s.solution_type for s in DEFAULT_CONFIG.solver_steps}
        assert SolutionType.SQUIRMBAG not in types


# ---------------------------------------------------------------------------
# Solve vs find-all defaults differ
# ---------------------------------------------------------------------------

class TestSolveVsFindAllDefaults:
    def test_als_overlap(self):
        solve = _default_solve_search()
        find_all = _default_find_all_search()
        assert solve.als_allow_overlap is False
        assert find_all.als_allow_overlap is True

    def test_tabling_dedup(self):
        solve = _default_solve_search()
        find_all = _default_find_all_search()
        assert solve.tabling_only_one_chain_per_elimination is True
        assert find_all.tabling_only_one_chain_per_elimination is False

    def test_tabling_als_in_chains(self):
        solve = _default_solve_search()
        find_all = _default_find_all_search()
        assert solve.tabling_allow_als_in_chains is False
        assert find_all.tabling_allow_als_in_chains is True

    def test_find_all_disabled_types(self):
        find_all = _default_find_all_search()
        assert SolutionType.TEMPLATE_SET in find_all.disabled_types
        assert SolutionType.FORCING_CHAIN_CONTRADICTION in find_all.disabled_types

    def test_solve_no_disabled_types(self):
        solve = _default_solve_search()
        assert len(solve.disabled_types) == 0


# ---------------------------------------------------------------------------
# step_overrides
# ---------------------------------------------------------------------------

class TestStepOverrides:
    def test_override_base_score(self):
        cfg = SolverConfig(
            step_overrides={SolutionType.X_WING: dict(base_score=200)},
        )
        assert cfg.step_config[SolutionType.X_WING].base_score == 200
        # Others unchanged
        assert cfg.step_config[SolutionType.SWORDFISH].base_score == 150

    def test_override_affects_solver_steps(self):
        cfg = SolverConfig(
            step_overrides={SolutionType.X_WING: dict(base_score=999)},
        )
        x_wing_cfg = next(
            s for s in cfg.solver_steps
            if s.solution_type == SolutionType.X_WING
        )
        assert x_wing_cfg.base_score == 999

    def test_override_affects_all_steps(self):
        cfg = SolverConfig(
            step_overrides={SolutionType.SQUIRMBAG: dict(enabled=True)},
        )
        types = {s.solution_type for s in cfg.solver_steps}
        assert SolutionType.SQUIRMBAG in types

    def test_override_preserves_aliases(self):
        cfg = SolverConfig(
            step_overrides={
                SolutionType.SIMPLE_COLORS_TRAP: dict(base_score=500),
            },
        )
        # Alias should share the overridden config
        assert cfg.step_config[SolutionType.SIMPLE_COLORS_WRAP].base_score == 500

    def test_all_steps_with_overrides(self):
        cfg = SolverConfig(
            step_overrides={
                SolutionType.TEMPLATE_SET: dict(all_steps_enabled=True),
            },
        )
        tmpl = next(
            s for s in cfg.all_steps
            if s.solution_type == SolutionType.TEMPLATE_SET
        )
        assert tmpl.all_steps_enabled is True


# ---------------------------------------------------------------------------
# difficulty_thresholds
# ---------------------------------------------------------------------------

class TestDifficultyThresholds:
    def test_override_threshold(self):
        cfg = SolverConfig(
            difficulty_thresholds={DifficultyType.HARD: 2000},
        )
        assert cfg._difficulty_max_score[DifficultyType.HARD] == 2000
        # Others unchanged
        assert cfg._difficulty_max_score[DifficultyType.EASY] == 800


# ---------------------------------------------------------------------------
# FishSearchConfig / KrakenFishSearchConfig / FishType
# ---------------------------------------------------------------------------

class TestFishConfig:
    def test_fish_type_ordering(self):
        assert FishType.BASIC < FishType.BASIC_FRANKEN < FishType.BASIC_FRANKEN_MUTANT

    def test_defaults(self):
        fc = FishSearchConfig()
        assert fc.search_fish is True
        assert fc.fish_type == FishType.BASIC_FRANKEN
        assert fc.min_size == 2
        assert fc.max_size == 4
        assert fc.max_fins == 5
        assert fc.max_endo_fins == 2

    def test_kraken_defaults(self):
        kc = KrakenFishSearchConfig()
        assert kc.search_kraken_fish is False
        assert kc.max_fins == 2
        assert kc.max_endo_fins == 0


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------

class TestFrozen:
    def test_solver_config_frozen(self):
        with pytest.raises(AttributeError):
            DEFAULT_CONFIG.solve_search = StepSearchConfig()

    def test_step_search_config_frozen(self):
        cfg = StepSearchConfig()
        with pytest.raises(AttributeError):
            cfg.chain_max_length = 10

    def test_fish_search_config_frozen(self):
        fc = FishSearchConfig()
        with pytest.raises(AttributeError):
            fc.max_fins = 10

    def test_step_config_is_copy(self):
        """step_config returns a copy — mutating it doesn't affect globals."""
        from hodoku.core.scoring import STEP_CONFIG
        cfg = DEFAULT_CONFIG.step_config
        original_score = STEP_CONFIG[SolutionType.X_WING].base_score
        cfg[SolutionType.X_WING] = None  # mutate the copy
        assert STEP_CONFIG[SolutionType.X_WING].base_score == original_score

    def test_difficulty_max_score_is_copy(self):
        """_difficulty_max_score returns a copy — mutating it doesn't affect globals."""
        from hodoku.core.scoring import DIFFICULTY_MAX_SCORE
        cfg = DEFAULT_CONFIG._difficulty_max_score
        original = DIFFICULTY_MAX_SCORE[DifficultyType.EASY]
        cfg[DifficultyType.EASY] = 0  # mutate the copy
        assert DIFFICULTY_MAX_SCORE[DifficultyType.EASY] == original
