"""Step-by-step validation of Full House, Naked Single, Hidden Single against HoDoKu.

For each test puzzle:
  1. Run HoDoKu (/vp) and parse its solution path.
  2. Run our SudokuSolver and collect steps.
  3. Assert every step matches in technique type, cell, and digit — in order.
"""

from __future__ import annotations

import pytest

from hodoku.core.types import SolutionType

pytestmark = pytest.mark.hodoku
from hodoku.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult, HodokuStep


# ---------------------------------------------------------------------------
# Puzzles that HoDoKu can solve using only Full House / Naked / Hidden Single
# ---------------------------------------------------------------------------

# A well-known easy puzzle solvable with singles only
EASY_PUZZLES = [
    # Classic "easy" — solvable with Naked / Hidden Singles
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079",
    # Another singles-only puzzle
    "003020600900305001001806400008102900700000008006708200002609500800203009005010300",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SINGLES = {SolutionType.FULL_HOUSE, SolutionType.NAKED_SINGLE, SolutionType.HIDDEN_SINGLE}


def _technique_to_solution_type(technique: str) -> SolutionType | None:
    """Map a HoDoKu technique name to one of the three singles SolutionTypes."""
    from tests.hodoku_harness import _NAME_MAP
    return _NAME_MAP.get(technique)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("puzzle", EASY_PUZZLES)
def test_singles_match_hodoku(puzzle: str, solve_with_hodoku) -> None:
    """Our step sequence must match HoDoKu's for singles-only puzzles."""
    hodoku: HodokuResult = solve_with_hodoku(puzzle)
    assert hodoku.solved, f"HoDoKu could not solve puzzle: {puzzle}"

    # Filter to only singles steps (skip any non-singles HoDoKu may emit)
    hodoku_singles: list[HodokuStep] = [
        s for s in hodoku.steps if s.solution_type in _SINGLES
    ]
    assert hodoku_singles, "HoDoKu produced no singles steps — wrong puzzle?"

    solver = SudokuSolver()
    our_result = solver.solve(puzzle)
    assert our_result.solved, "Our solver could not solve the puzzle"

    # Compare step counts
    assert len(our_result.steps) == len(hodoku_singles), (
        f"Step count mismatch: ours={len(our_result.steps)}, "
        f"hodoku={len(hodoku_singles)}"
    )

    for i, (ours, theirs) in enumerate(zip(our_result.steps, hodoku_singles)):
        assert ours.type == theirs.solution_type, (
            f"Step {i}: type mismatch ours={ours.type.name} theirs={theirs.solution_type}"
        )
        assert ours.indices == theirs.indices, (
            f"Step {i} ({ours.type.name}): cell mismatch "
            f"ours={ours.indices} theirs={theirs.indices}"
        )
        assert ours.values == theirs.values, (
            f"Step {i} ({ours.type.name}): value mismatch "
            f"ours={ours.values} theirs={theirs.values}"
        )


@pytest.mark.parametrize("puzzle", EASY_PUZZLES)
def test_solver_produces_correct_solution(puzzle: str) -> None:
    """Solved grid must match a brute-force reference (no HoDoKu needed)."""
    from hodoku.core.grid import Grid

    solver = SudokuSolver()
    result = solver.solve(puzzle)
    assert result.solved

    # Verify every row, column, and box contains each digit exactly once
    g = Grid()
    g.set_sudoku(puzzle)
    for idx, step in enumerate(result.steps):
        for cell, val in zip(step.indices, step.values):
            g.set_cell(cell, val)
        for cand in step.candidates_to_delete:
            g.del_candidate(cand.index, cand.value)

    from hodoku.core.grid import LINES, COLS, BLOCKS
    for unit in list(LINES) + list(COLS) + list(BLOCKS):
        digits = {g.values[j] for j in unit}
        assert digits == set(range(1, 10)), f"Unit {unit} is not complete: {digits}"
