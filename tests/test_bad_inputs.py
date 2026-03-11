"""Public API input validation tests.

Tests that the Solver class handles malformed and edge-case puzzle strings
correctly, without requiring HoDoKu or Java.

All four public Solver methods (solve, get_hint, rate, find_all_steps) share
the same validation path, so format-error tests verify all four.
"""

import pytest

from hodoku.api import Solver

# A known valid easy puzzle and its solution.
EASY_PUZZLE = "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
EASY_SOLUTION = "534678912672195348198342567859761423426853791713924856961537284287419635345286179"

ALL_EMPTY = "0" * 81
SINGLE_GIVEN = "5" + "0" * 80  # only r1c1 = 5


@pytest.fixture
def solver() -> Solver:
    return Solver()


# ---------------------------------------------------------------------------
# Format errors — should raise ValueError from all four public methods
# ---------------------------------------------------------------------------

FORMAT_ERROR_CASES = [
    ("too_short",       "123"),
    ("too_long",        "0" * 82),
    ("eighty_chars",    "0" * 80),
    ("invalid_letter",  "A" * 81),
    ("invalid_symbol",  "0" * 40 + "?" + "0" * 40),
    ("spaces",          " " * 81),
    ("empty_string",    ""),
]


@pytest.mark.parametrize("label,puzzle", FORMAT_ERROR_CASES, ids=[c[0] for c in FORMAT_ERROR_CASES])
def test_solve_raises_on_format_error(solver, label, puzzle):
    with pytest.raises(ValueError):
        solver.solve(puzzle)


@pytest.mark.parametrize("label,puzzle", FORMAT_ERROR_CASES, ids=[c[0] for c in FORMAT_ERROR_CASES])
def test_get_hint_raises_on_format_error(solver, label, puzzle):
    with pytest.raises(ValueError):
        solver.get_hint(puzzle)


@pytest.mark.parametrize("label,puzzle", FORMAT_ERROR_CASES, ids=[c[0] for c in FORMAT_ERROR_CASES])
def test_rate_raises_on_format_error(solver, label, puzzle):
    with pytest.raises(ValueError):
        solver.rate(puzzle)


@pytest.mark.parametrize("label,puzzle", FORMAT_ERROR_CASES, ids=[c[0] for c in FORMAT_ERROR_CASES])
def test_find_all_steps_raises_on_format_error(solver, label, puzzle):
    with pytest.raises(ValueError):
        solver.find_all_steps(puzzle)


# ---------------------------------------------------------------------------
# Duplicate digit in a house — should raise ValueError
# ---------------------------------------------------------------------------

# Two 5s in the same row (row 0, cells 0 and 1)
DUP_IN_ROW = "550000000" + "0" * 72
# Two 5s in the same column (col 0, cells 0 and 9)
DUP_IN_COL = "500000000" + "500000000" + "0" * 63
# Two 5s in the same box (box 0: r0c0=cell 0, r1c1=cell 10)
DUP_IN_BOX = "500000000" + "0" + "5" + "0" * 7 + "0" * 63


def test_solve_raises_on_duplicate_in_row(solver):
    with pytest.raises(ValueError, match="row|house|duplicate"):
        solver.solve(DUP_IN_ROW)


def test_solve_raises_on_duplicate_in_col(solver):
    with pytest.raises(ValueError, match="col|house|duplicate"):
        solver.solve(DUP_IN_COL)


def test_solve_raises_on_duplicate_in_box(solver):
    with pytest.raises(ValueError, match="box|house|duplicate"):
        solver.solve(DUP_IN_BOX)


# ---------------------------------------------------------------------------
# Valid edge cases — must NOT raise
# ---------------------------------------------------------------------------

def test_already_solved_returns_no_steps(solver):
    """A fully-filled valid grid: solved=True with zero steps."""
    result = solver.solve(EASY_SOLUTION)
    assert result.solved is True
    assert result.steps == []


def test_already_solved_solution_matches_input(solver):
    result = solver.solve(EASY_SOLUTION)
    assert result.solution == EASY_SOLUTION


def test_all_empty_grid_solves(solver):
    """An all-zero grid has many solutions; brute force should find one."""
    result = solver.solve(ALL_EMPTY)
    assert result.solved is True
    # Result must be a valid completed grid (all digits 1-9)
    assert len(result.solution) == 81
    assert all(c in "123456789" for c in result.solution)


def test_single_given_solves(solver):
    """A grid with only one given should terminate without crashing."""
    result = solver.solve(SINGLE_GIVEN)
    assert result.solved is True


def test_normal_puzzle_solves(solver):
    result = solver.solve(EASY_PUZZLE)
    assert result.solved is True
    assert result.solution == EASY_SOLUTION
    assert result.score > 0


def test_dots_accepted_as_empty(solver):
    """'.' should be accepted as an alternative empty-cell marker."""
    dot_puzzle = EASY_PUZZLE.replace("0", ".")
    result = solver.solve(dot_puzzle)
    assert result.solved is True


def test_get_hint_on_valid_puzzle_returns_step(solver):
    step = solver.get_hint(EASY_PUZZLE)
    assert step is not None


def test_get_hint_on_solved_puzzle_returns_none(solver):
    step = solver.get_hint(EASY_SOLUTION)
    assert step is None


def test_rate_on_valid_puzzle(solver):
    rating = solver.rate(EASY_PUZZLE)
    assert rating.score > 0


def test_find_all_steps_on_valid_puzzle(solver):
    steps = solver.find_all_steps(EASY_PUZZLE)
    assert len(steps) > 0
