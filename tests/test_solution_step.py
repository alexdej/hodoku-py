"""Unit tests for SolutionStep and Candidate formatting."""

from __future__ import annotations

import pytest

from hodoku.core.solution_step import Candidate, SolutionStep
from hodoku.core.types import SolutionType

pytestmark = pytest.mark.unit


class TestSolutionTypeIsSingle:
    def test_full_house_is_single(self):
        assert SolutionType.FULL_HOUSE.is_single() is True

    def test_hidden_single_is_single(self):
        assert SolutionType.HIDDEN_SINGLE.is_single() is True

    def test_naked_single_is_single(self):
        assert SolutionType.NAKED_SINGLE.is_single() is True

    def test_non_single(self):
        assert SolutionType.NAKED_PAIR.is_single() is False


class TestCandidateStr:
    def test_basic(self):
        assert str(Candidate(40, 5)) == "r5c5<>5"

    def test_first_cell(self):
        assert str(Candidate(0, 1)) == "r1c1<>1"

    def test_last_cell(self):
        assert str(Candidate(80, 9)) == "r9c9<>9"

    def test_row_col_mapping(self):
        # index 17 = row 2, col 9
        assert str(Candidate(17, 3)) == "r2c9<>3"


class TestSolutionStepStr:
    def test_placement_single_cell(self):
        step = SolutionStep(SolutionType.HIDDEN_SINGLE)
        step.add_index(43)   # r5c8
        step.add_value(4)
        assert str(step) == "Hidden Single: r5c8=4"

    def test_placement_multiple_cells(self):
        step = SolutionStep(SolutionType.NAKED_PAIR)
        step.add_index(0)
        step.add_value(2)
        step.add_index(1)
        step.add_value(3)
        assert str(step) == "Naked Pair: r1c1=2, r1c2=3"

    def test_elimination(self):
        step = SolutionStep(SolutionType.LOCKED_CANDIDATES_2)
        step.add_candidate_to_delete(10, 7)  # r2c2
        step.add_candidate_to_delete(19, 7)  # r3c2
        assert str(step) == "Locked Candidates Type 2 (Claiming): r2c2<>7, r3c2<>7"

    def test_no_indices_no_eliminations(self):
        step = SolutionStep(SolutionType.HIDDEN_SINGLE)
        assert str(step) == "Hidden Single"

    def test_repr(self):
        step = SolutionStep(SolutionType.FULL_HOUSE)
        step.add_index(8)
        step.add_value(9)
        assert repr(step) == "SolutionStep(FULL_HOUSE, indices=[8], values=[9])"
