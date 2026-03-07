"""Tests for BruteForceSolver — last-resort backtracking."""

from __future__ import annotations

import pytest

from hodoku.core.grid import Grid
from hodoku.core.types import SolutionType
from hodoku.solver.brute_force import BruteForceSolver
from hodoku.solver.solver import SudokuSolver


# ---------------------------------------------------------------------------
# Unit tests for BruteForceSolver in isolation
# ---------------------------------------------------------------------------

def _make_grid(puzzle: str) -> Grid:
    g = Grid()
    g.set_sudoku(puzzle)
    return g


def _is_valid_solution(values: list[int]) -> bool:
    """Check that a 81-int list is a valid, complete sudoku."""
    if 0 in values:
        return False
    for i in range(9):
        row = values[i*9:(i+1)*9]
        col = [values[i + j*9] for j in range(9)]
        br, bc = (i // 3) * 3, (i % 3) * 3
        box = [values[(br + r)*9 + bc + c] for r in range(3) for c in range(3)]
        if set(row) != set(range(1, 10)):
            return False
        if set(col) != set(range(1, 10)):
            return False
        if set(box) != set(range(1, 10)):
            return False
    return True


# A nearly-solved grid (one empty cell) — guaranteed to work regardless of other solvers
_NEAR_DONE = "812753649943682175675491283154237896369845721287169534521974368438526917796318450"
_NEAR_DONE_SOL = 2  # cell 80 should be 2


def test_brute_force_single_cell() -> None:
    """BruteForceSolver correctly places the last empty cell."""
    grid = _make_grid(_NEAR_DONE)
    solver = BruteForceSolver(grid)
    step = solver.get_step(SolutionType.BRUTE_FORCE)
    assert step is not None
    assert step.type is SolutionType.BRUTE_FORCE
    assert step.indices == [80]
    assert step.values == [_NEAR_DONE_SOL]


def test_brute_force_produces_valid_solution() -> None:
    """Backtracking fills a partial grid to a valid complete solution."""
    # A puzzle solvable by brute force alone (no candidates eliminated yet)
    puzzle = "000000000000000000000000000000000000000000000000000000000000000000000000000000001"
    grid = _make_grid(puzzle)
    solver = BruteForceSolver(grid)

    # Drain all steps into the grid
    from hodoku.solver.solver import _apply_step, _PLACEMENT_TYPES
    for _ in range(80):
        step = solver.get_step(SolutionType.BRUTE_FORCE)
        if step is None:
            break
        grid.set_cell(step.indices[0], step.values[0])

    assert _is_valid_solution(grid.values)


def test_brute_force_returns_none_when_solved() -> None:
    """get_step returns None if the grid is already completely filled."""
    solved = "812753649943682175675491283154237896369845721287169534521974368438526917796318452"
    grid = _make_grid(solved)
    solver = BruteForceSolver(grid)
    assert solver.get_step(SolutionType.BRUTE_FORCE) is None


# ---------------------------------------------------------------------------
# Integration tests: full solve loop with brute force as backstop
# ---------------------------------------------------------------------------

# Easy puzzle — solved entirely by singles, brute force should NOT be needed
_EASY = "530070000600195000098000060800060003400803001700020006060000280000419005000080079"

# Medium-hard puzzle where our current solver might exhaust known techniques
_MEDIUM = "000000604000064000100800000078609050950003860000000007830095710000028000009000000"


@pytest.mark.parametrize("label,puzzle", [
    ("easy",   _EASY),
    ("medium", _MEDIUM),
])
def test_solver_completes_with_brute_force_backstop(label: str, puzzle: str) -> None:
    """Solver always reaches solved=True with brute force as last resort."""
    solver = SudokuSolver()
    result = solver.solve(puzzle)
    assert result.solved, f"[{label}] Solver failed to reach a solution"


def test_easy_puzzle_does_not_use_brute_force() -> None:
    """Easy puzzles are solved by logic alone — brute force should never fire."""
    solver = SudokuSolver()
    result = solver.solve(_EASY)
    assert result.solved
    bf_steps = [s for s in result.steps if s.type is SolutionType.BRUTE_FORCE]
    assert bf_steps == [], f"Expected no brute force steps, got {bf_steps}"
