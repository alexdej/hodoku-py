"""Technique-isolation tests from HoDoKu's reglib-1.3.txt.

Each test case:
  1. Reconstructs a specific pencilmark (PM) board state from the library entry.
  2. Asks our solver to find the next step of the specified technique.
  3. Verifies that the returned eliminations/placements match exactly.

Key properties:
  - No HoDoKu/Java required — board state is fully self-contained.
  - Independent of solve-path ordering: each entry tests ONE technique in
    isolation on a fixed PM.
  - Complementary to tests/regression/ (exemplars), which validates full
    head-to-head solve paths against HoDoKu's CLI.

Board reconstruction
--------------------
  givens_placed  → Grid.set_sudoku() (standard candidate elimination)
  deleted_cands  → Grid.del_candidate() for each listed (digit, row, col)

This mirrors Sudoku2.setSudoku(libraryFormat) in RegressionTester.java.

Fail cases
----------
Entries with variant '-x' require that the technique NOT fire.

Techniques not yet implemented
-------------------------------
Entries whose technique code is in _SKIP_CODES are skipped outright because
the corresponding solver isn't implemented yet.  All other entries run and
naturally pass or fail — failing tests reveal real gaps in our implementation.
"""

from __future__ import annotations

import pytest

from hodoku.core.grid import Grid
from hodoku.core.types import SolutionType
from hodoku.solver.step_finder import SudokuStepFinder
from tests.reglib.reglib_parser import REGLIB_FILE, ReglibEntry

# Technique codes with no implementation at all — skip rather than fail.
_SKIP_CODES = frozenset({
    "1101",  # Sue de Coq
    "1201",  # Template Set
    "1202",  # Template Delete
    "1301",  # Forcing Chain Contradiction
    "1302",  # Forcing Chain Verity
    "1303",  # Forcing Net Contradiction
    "1304",  # Forcing Net Verity
})


def _build_grid(entry: ReglibEntry) -> Grid:
    """Reconstruct the PM board state described by the reglib entry."""
    grid = Grid()
    grid.set_sudoku(entry.givens_placed)
    for digit, row, col in entry.deleted_candidates:
        grid.del_candidate((row - 1) * 9 + (col - 1), digit)
    return grid


def _find_step(finder: SudokuStepFinder, sol_types: frozenset[SolutionType]):
    """Try each SolutionType in turn; return the first step found."""
    for sol_type in sorted(sol_types, key=lambda t: t.value):
        step = finder.get_step(sol_type)
        if step is not None:
            return step
    return None


def test_reglib_technique(reglib_entry: ReglibEntry) -> None:
    if not REGLIB_FILE.exists():
        pytest.skip("reglib-1.3.txt not found (expected at ../HoDoKu/reglib-1.3.txt)")

    entry = reglib_entry

    if entry.technique_code in _SKIP_CODES:
        pytest.skip(f"Technique {entry.technique_code} not yet implemented")

    if not entry.solution_types:
        pytest.skip(f"Unknown technique code {entry.technique_code!r}")

    grid = _build_grid(entry)
    finder = SudokuStepFinder(grid)
    step = _find_step(finder, entry.solution_types)

    # --- Fail case: technique must NOT fire ---
    if entry.fail_case:
        assert step is None, (
            f"Technique {entry.technique_code} should NOT fire on this board, "
            f"but found: {step}"
        )
        return

    # --- Normal case: technique must fire with correct output ---
    assert step is not None, (
        f"Technique {entry.technique_code} did not fire on this board.\n"
        f"  givens_placed:  {entry.givens_placed}\n"
        f"  deleted_cands:  {entry.deleted_candidates}\n"
        f"  expected elims: {entry.eliminations}\n"
        f"  expected places: {entry.placements}"
    )

    if entry.eliminations:
        expected = frozenset(
            ((r - 1) * 9 + (c - 1), d) for d, r, c in entry.eliminations
        )
        actual = frozenset(
            (cand.index, cand.value) for cand in step.candidates_to_delete
        )
        assert actual == expected, (
            f"Technique {entry.technique_code} elimination mismatch:\n"
            f"  expected: {_fmt_cell_set(expected)}\n"
            f"  actual:   {_fmt_cell_set(actual)}"
        )

    elif entry.placements:
        expected = frozenset(
            ((r - 1) * 9 + (c - 1), d) for d, r, c in entry.placements
        )
        actual = frozenset(zip(step.indices, step.values))
        assert actual == expected, (
            f"Technique {entry.technique_code} placement mismatch:\n"
            f"  expected: {_fmt_cell_set(expected)}\n"
            f"  actual:   {_fmt_cell_set(actual)}"
        )


def _fmt_cell_set(s: frozenset[tuple[int, int]]) -> str:
    """Format a set of (cell_index, digit) pairs as 'r1c2<>3' strings."""
    parts = []
    for idx, digit in sorted(s):
        r, c = divmod(idx, 9)
        parts.append(f"r{r+1}c{c+1}<>{digit}")
    return ", ".join(parts)
