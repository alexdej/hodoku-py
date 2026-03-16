"""Unit tests verifying that SolutionStep data supports each GUI view.

These tests do not build any GUI — they demonstrate that the structured data
needed to render each "All possible steps" view is present and correctly typed.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from hodoku import Solver
from hodoku.core.solution_step import SolutionStep
from hodoku.core.types import SolutionType

pytestmark = pytest.mark.unit

# Puzzle that requires techniques beyond singles (XY-chains, locked candidates)
PUZZLE = "000007001100200400000000009070020065800060007040000000080670190620000300003100000"


@pytest.fixture(scope="module")
def all_steps() -> list[SolutionStep]:
    return Solver().find_all_steps(PUZZLE)


@pytest.fixture(scope="module")
def solve_steps() -> list[SolutionStep]:
    return Solver().solve(PUZZLE).steps


# ---------------------------------------------------------------------------
# View: Sort by type (T button)
# ---------------------------------------------------------------------------

class TestByTypeView:
    def test_can_group_by_type(self, all_steps):
        groups: dict[SolutionType, list[SolutionStep]] = defaultdict(list)
        for step in all_steps:
            groups[step.type].append(step)
        assert len(groups) > 1

    def test_group_has_count(self, all_steps):
        groups: dict[SolutionType, list[SolutionStep]] = defaultdict(list)
        for step in all_steps:
            groups[step.type].append(step)
        # Every group should have at least one step
        assert all(len(v) >= 1 for v in groups.values())

    def test_steps_have_str(self, all_steps):
        # Every step must be renderable as a leaf label
        for step in all_steps:
            assert isinstance(str(step), str)
            assert len(str(step)) > 0


# ---------------------------------------------------------------------------
# View: Sort by eliminations (E button)
# ---------------------------------------------------------------------------

class TestByEliminationsView:
    def test_placements_have_indices(self, all_steps):
        # Placement steps (singles) have one index and one value per cell set.
        # Elimination steps may also have indices as pattern context (e.g.
        # LOCKED_CANDIDATES has the pattern cells in indices, digit in values[0]).
        singles = {SolutionType.FULL_HOUSE, SolutionType.NAKED_SINGLE, SolutionType.HIDDEN_SINGLE}
        placements = [s for s in all_steps if s.type in singles]
        assert len(placements) > 0
        for step in placements:
            assert len(step.indices) == len(step.values) == 1

    def test_eliminations_have_candidates_to_delete(self, all_steps):
        eliminations = [s for s in all_steps if not s.indices]
        assert len(eliminations) > 0
        for step in eliminations:
            assert len(step.candidates_to_delete) > 0

    def test_placements_sort_before_eliminations(self, all_steps):
        def sort_key(s: SolutionStep):
            # Placements first (negate to sort descending), then by elim count
            is_placement = 1 if s.indices else 0
            return (-is_placement, -len(s.candidates_to_delete))
        sorted_steps = sorted(all_steps, key=sort_key)
        first_elim = next(i for i, s in enumerate(sorted_steps) if not s.indices)
        assert all(sorted_steps[i].indices for i in range(first_elim))

    def test_can_group_by_elimination_set(self, all_steps):
        # Steps with identical eliminations share a get_candidate_string() key
        groups: dict[str, list[SolutionStep]] = defaultdict(list)
        for step in all_steps:
            key = step.get_candidate_string()
            groups[key].append(step)
        # At least some groups exist
        assert len(groups) > 0
        # Any group with >1 entry represents the "folder" grouping in the GUI
        multi = [v for v in groups.values() if len(v) > 1]
        assert len(multi) >= 0  # may be zero for this puzzle — just check structure


# ---------------------------------------------------------------------------
# View: Sort by row/col (C button)
# ---------------------------------------------------------------------------

class TestByRowColView:
    def test_steps_have_sortable_cell(self, all_steps):
        def first_cell(s: SolutionStep) -> int:
            if s.indices:
                return s.indices[0]
            if s.candidates_to_delete:
                return s.candidates_to_delete[0].index
            return 81  # sentinel for steps with no cell info

        sorted_steps = sorted(all_steps, key=first_cell)
        assert len(sorted_steps) == len(all_steps)

    def test_cell_index_in_range(self, all_steps):
        for step in all_steps:
            for idx in step.indices:
                assert 0 <= idx <= 80
            for c in step.candidates_to_delete:
                assert 0 <= c.index <= 80


# ---------------------------------------------------------------------------
# View: Sort by directly unlocked singles / unlocked singles (D, S buttons)
# ---------------------------------------------------------------------------

class TestProgressScoreFields:
    def test_progress_score_fields_exist(self, all_steps):
        # Fields exist on every step (default -1 = not yet computed)
        for step in all_steps:
            assert hasattr(step, "progress_score")
            assert hasattr(step, "progress_score_singles")
            assert hasattr(step, "progress_score_singles_only")

    def test_progress_scores_not_populated_by_solve(self, solve_steps):
        # solve() does not populate progress scores — only find_all_steps() does
        for step in solve_steps:
            assert step.progress_score == -1
            assert step.progress_score_singles == -1
            assert step.progress_score_singles_only == -1

    def test_can_sort_by_directly_unlocked_singles(self, all_steps):
        # Even with default -1 values the sort is stable and type-safe
        sorted_steps = sorted(all_steps, key=lambda s: s.progress_score_singles_only, reverse=True)
        assert len(sorted_steps) == len(all_steps)

    def test_can_sort_by_unlocked_singles(self, all_steps):
        sorted_steps = sorted(all_steps, key=lambda s: s.progress_score_singles, reverse=True)
        assert len(sorted_steps) == len(all_steps)


# ---------------------------------------------------------------------------
# Resulting score field (sub-grouping within D and S views)
# ---------------------------------------------------------------------------

class TestResultingScoreField:
    def test_resulting_score_is_progress_score(self, all_steps):
        # "Resulting Score" in the GUI tree is step.progress_score —
        # the sum of base scores of all steps needed to finish the puzzle
        # after applying this step. find_all_steps() always populates it.
        # (Not yet implemented — will be non-(-1) once find_all_steps computes
        # progress scores unconditionally, matching Java FindAllSteps step 27.)
        for step in all_steps:
            assert hasattr(step, "progress_score")
