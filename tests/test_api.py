"""Unit tests for the public Solver API (api.py)."""

from __future__ import annotations

import pytest

from hodoku import Solver
from hodoku.core.types import DifficultyType

pytestmark = pytest.mark.unit

# Simple puzzle solvable with singles only (EASY level)
EASY_PUZZLE   = "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
EASY_SOLUTION = "534678912672195348198342567859761423426853791713924856961537284287419635345286179"

# A medium puzzle that requires locked candidates / subsets
MEDIUM_PUZZLE = "000000010400000000020000000000050407008000300001090000300400200050100000000806000"

# A pre-solved grid (EASY_SOLUTION itself)
SOLVED_PUZZLE = EASY_SOLUTION


# ---------------------------------------------------------------------------
# solve()
# ---------------------------------------------------------------------------

class TestSolve:
    def test_easy_puzzle_is_solved(self):
        result = Solver().solve(EASY_PUZZLE)
        assert result.solved is True

    def test_solution_string_matches(self):
        result = Solver().solve(EASY_PUZZLE)
        assert result.solution == EASY_SOLUTION

    def test_solution_is_81_chars(self):
        result = Solver().solve(EASY_PUZZLE)
        assert len(result.solution) == 81
        assert result.solution.isdigit()

    def test_steps_non_empty(self):
        result = Solver().solve(EASY_PUZZLE)
        assert len(result.steps) > 0

    def test_level_is_not_incomplete(self):
        result = Solver().solve(EASY_PUZZLE)
        assert result.level != DifficultyType.INCOMPLETE

    def test_score_positive(self):
        result = Solver().solve(EASY_PUZZLE)
        assert result.score > 0

    def test_each_step_has_type(self):
        result = Solver().solve(EASY_PUZZLE)
        for step in result.steps:
            assert step.type is not None

    def test_already_solved_puzzle(self):
        result = Solver().solve(SOLVED_PUZZLE)
        assert result.solved is True
        assert result.solution == SOLVED_PUZZLE
        assert result.steps == []


# ---------------------------------------------------------------------------
# get_hint()
# ---------------------------------------------------------------------------

class TestGetHint:
    def test_returns_step_for_unsolved(self):
        hint = Solver().get_hint(EASY_PUZZLE)
        assert hint is not None

    def test_hint_has_type(self):
        hint = Solver().get_hint(EASY_PUZZLE)
        assert hint.type is not None

    def test_returns_none_for_solved(self):
        hint = Solver().get_hint(SOLVED_PUZZLE)
        assert hint is None

    def test_hint_advances_puzzle(self):
        """Two successive hints on the same grid state return the same first step."""
        s = Solver()
        hint1 = s.get_hint(EASY_PUZZLE)
        hint2 = s.get_hint(EASY_PUZZLE)
        # get_hint is stateless — same puzzle -> same hint
        assert hint1.type == hint2.type


# ---------------------------------------------------------------------------
# rate()
# ---------------------------------------------------------------------------

class TestRate:
    def test_returns_rating_result(self):
        from hodoku.api import RatingResult
        result = Solver().rate(EASY_PUZZLE)
        assert isinstance(result, RatingResult)

    def test_easy_level(self):
        result = Solver().rate(EASY_PUZZLE)
        assert result.level == DifficultyType.EASY

    def test_score_matches_solve(self):
        s = Solver()
        rating = s.rate(EASY_PUZZLE)
        solve  = s.solve(EASY_PUZZLE)
        assert rating.score == solve.score
        assert rating.level == solve.level

    def test_incomplete_for_unsolvable(self):
        # 17 givens but contradictory — no solution possible
        bad = "1" * 81  # all 1s is invalid
        result = Solver().rate(bad)
        assert result.level == DifficultyType.INCOMPLETE


# ---------------------------------------------------------------------------
# find_all_steps()
# ---------------------------------------------------------------------------

class TestFindAllSteps:
    def test_returns_list(self):
        steps = Solver().find_all_steps(EASY_PUZZLE)
        assert isinstance(steps, list)

    def test_non_empty_on_unsolved(self):
        steps = Solver().find_all_steps(EASY_PUZZLE)
        assert len(steps) > 0

    def test_all_steps_have_type(self):
        steps = Solver().find_all_steps(EASY_PUZZLE)
        for step in steps:
            assert step.type is not None

    def test_empty_on_solved(self):
        # A solved grid has no candidates to eliminate or cells to fill
        steps = Solver().find_all_steps(SOLVED_PUZZLE)
        assert steps == []
