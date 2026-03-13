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
"""

from __future__ import annotations

import pytest

from hodoku.core.grid import Grid
from hodoku.core.types import SolutionType
from hodoku.solver.step_finder import SudokuStepFinder, _ALS_TYPES
from tests.reglib.reglib_parser import REGLIB_FILE, ReglibEntry

# Tests that also fail in Java HoDoKu v2.2.0 (reglib-1.3.txt).
# ALS-XY-Chain: needs bidirectional RC traversal or chain length >6,
# which Java's default allStepsAlsChainForwardOnly=true / length=6 can't find.
_JAVA_XFAIL_LINES = frozenset({1445, 1453, 1454, 1455, 1459})

# Tests that require cross-type siamese (basic + finned fish sharing a base),
# which Java supports by running getAllFishes with fishType=UNDEFINED before
# applying siamese.  Our implementation runs basic and finned separately.
_CROSS_TYPE_SIAMESE_XFAIL = frozenset({724})

# Tests with search spaces too large for pure Python (require C accelerator).
# Finned Mutant Whale (size 6): C(24,6)=134K base combos × cover search.
_NEEDS_C_ACCEL_LINES = frozenset({763})

def _has_c_accel() -> bool:
    from hodoku.solver.fish import _accel
    return _accel is not None


def _build_grid(entry: ReglibEntry) -> Grid:
    """Reconstruct the PM board state described by the reglib entry."""
    grid = Grid()
    grid.set_sudoku(entry.givens_placed)
    for digit, row, col in entry.deleted_candidates:
        grid.del_candidate((row - 1) * 9 + (col - 1), digit)
    return grid


_ALS_OVERLAP_CODES = frozenset({"0902", "0903", "0904"})

# Grouped chain codes / variants that require ALS nodes in tabling chains
# (mirrors RegressionTester.java option flags)
_ALS_TABLING_CODES: dict[str, frozenset[int]] = {
    "0709": frozenset({2}),         # Grouped CNL variant 2
    "0710": frozenset({3, 4}),      # Grouped DNL variants 3, 4
    "0711": frozenset({3, 4}),      # Grouped AIC variants 3, 4
}


def _find_all_steps(
    finder: SudokuStepFinder,
    sol_types: frozenset[SolutionType],
    allow_overlap: bool = False,
    for_candidate: int = -1,
    allow_als_in_tabling: bool = False,
    grid: 'Grid | None' = None,
) -> list:
    """Return all steps of any of the given SolutionTypes."""
    results = []
    for sol_type in sorted(sol_types, key=lambda t: t.value):
        if allow_overlap and sol_type in _ALS_TYPES:
            results.extend(finder._als.find_all(sol_type, allow_overlap=True))
        elif allow_als_in_tabling and grid is not None:
            from hodoku.solver.tabling import TablingSolver
            ts = TablingSolver(grid)
            results.extend(ts.find_all_nice_loops(
                with_als_nodes=True, target_type=sol_type,
            ))
        else:
            results.extend(finder.find_all(sol_type, for_candidate=for_candidate))
    return results


def test_reglib_technique(reglib_entry: ReglibEntry) -> None:
    entry = reglib_entry

    if entry.commented_out:
        pytest.skip("Commented out in reglib-1.3.txt (also fails in HoDoKu v2.2.0)")

    if entry.line_num in _JAVA_XFAIL_LINES:
        pytest.xfail("Also fails in Java HoDoKu v2.2.0 (chain search limitations)")

    if entry.line_num in _CROSS_TYPE_SIAMESE_XFAIL:
        pytest.xfail("Requires cross-type siamese (basic+finned in one pass)")

    if entry.line_num in _NEEDS_C_ACCEL_LINES and not _has_c_accel():
        pytest.skip("Requires C accelerator; run: pip install -e . (needs a C compiler)")

    if not entry.solution_types:
        pytest.fail(f"Technique {entry.technique_code} not yet implemented")

    allow_overlap = (
        entry.variant == 2 and entry.technique_code in _ALS_OVERLAP_CODES
    )

    # Check if this variant needs ALS nodes in tabling chains
    als_variants = _ALS_TABLING_CODES.get(entry.technique_code)
    allow_als_in_tabling = (
        als_variants is not None
        and entry.variant is not None
        and entry.variant in als_variants
    )

    # Extract target digit for fish solver optimization (search one digit
    # instead of all 9).  candidates_field is e.g. "3" for digit 3.
    for_candidate = -1
    if len(entry.candidates_field) == 1 and entry.candidates_field.isdigit():
        for_candidate = int(entry.candidates_field)

    grid = _build_grid(entry)
    finder = SudokuStepFinder(grid)
    steps = _find_all_steps(
        finder, entry.solution_types, allow_overlap=allow_overlap,
        for_candidate=for_candidate,
        allow_als_in_tabling=allow_als_in_tabling,
        grid=grid,
    )

    # --- Fail case: technique must NOT fire ---
    if entry.fail_case:
        assert not steps, (
            f"Technique {entry.technique_code} should NOT fire on this board, "
            f"but found: {steps[0]}"
        )
        return

    # --- Normal case: at least one step must match expected output ---
    assert steps, (
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
        actual_sets = [
            frozenset((cand.index, cand.value) for cand in step.candidates_to_delete)
            for step in steps
        ]
        assert expected in actual_sets, (
            f"Technique {entry.technique_code} elimination mismatch — "
            f"expected set not found among {len(steps)} step(s):\n"
            f"  expected: {_fmt_cell_set(expected)}\n"
            f"  found:    {[_fmt_cell_set(s) for s in actual_sets]}"
        )

    elif entry.placements:
        expected = frozenset(
            ((r - 1) * 9 + (c - 1), d) for d, r, c in entry.placements
        )
        actual_sets = [
            frozenset(zip(step.indices, step.values)) for step in steps
        ]
        assert expected in actual_sets, (
            f"Technique {entry.technique_code} placement mismatch — "
            f"expected set not found among {len(steps)} step(s):\n"
            f"  expected: {_fmt_cell_set(expected)}\n"
            f"  found:    {[_fmt_cell_set(s) for s in actual_sets]}"
        )


def _fmt_cell_set(s: frozenset[tuple[int, int]]) -> str:
    """Format a set of (cell_index, digit) pairs as 'r1c2<>3' strings."""
    parts = []
    for idx, digit in sorted(s):
        r, c = divmod(idx, 9)
        parts.append(f"r{r+1}c{c+1}<>{digit}")
    return ", ".join(parts)
