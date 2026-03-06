"""HoDoKu validation for Single-Digit Patterns: Skyscraper, 2-String Kite, Empty Rectangle.

Strategy: rather than full step-by-step path comparison (which requires puzzles
solvable *only* by rows 1-9), we collect all row-9 eliminations produced by each
solver and assert they match.  This is valid because:
  - our solver applies row-9 techniques only when the same puzzle state is reached
  - any disagreement means our technique finds a wrong or missing elimination
"""

from __future__ import annotations

import pytest

from hodoku_py.core.types import SolutionType
from hodoku_py.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult

pytestmark = pytest.mark.hodoku

_ROW9_TYPES = frozenset({
    SolutionType.SKYSCRAPER,
    SolutionType.TWO_STRING_KITE,
    SolutionType.EMPTY_RECTANGLE,
})

# Puzzles used: verified to produce row-9 steps that match HoDoKu.
# Each entry is (label, puzzle_string, expected_technique).
SINGLE_DIGIT_PUZZLES = [
    # Skyscraper: 7 in r2c6,r4c4 (connected by r24c2) => r3c4,r5c6<>7
    # HoDoKu uses only rows 1-9 techniques (clean puzzle).
    (
        "skyscraper",
        "009060370402090000000000010306009000021430000000001007010000090000070028600300050",
        SolutionType.SKYSCRAPER,
    ),
    # 2-String Kite: 1 in r4c6,r7c9 (connected by r7c5,r9c6) => r4c9<>1
    (
        "two_string_kite",
        "008600000000759000600100090000000830906000005002405000005004380301802006000000200",
        SolutionType.TWO_STRING_KITE,
    ),
    # Empty Rectangle: 2 in b4 (r14c8) => r1c1<>2
    (
        "empty_rectangle",
        "096403800000000000000090040007600000001800070084700301000006200000104705040080030",
        SolutionType.EMPTY_RECTANGLE,
    ),
]


@pytest.mark.parametrize("label,puzzle,technique", SINGLE_DIGIT_PUZZLES)
def test_single_digit_matches_hodoku(
    label: str, puzzle: str, technique: SolutionType, solve_with_hodoku
) -> None:
    hodoku: HodokuResult = solve_with_hodoku(puzzle)

    # Collect row-9 eliminations from HoDoKu
    hodoku_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in hodoku.steps:
        if step.solution_type in _ROW9_TYPES:
            hodoku_elims.setdefault(step.solution_type, []).extend(step.eliminations)

    if technique not in hodoku_elims:
        pytest.skip(f"HoDoKu did not use {technique.name} on this puzzle")

    # Collect row-9 eliminations from our solver
    solver = SudokuSolver()
    our_result = solver.solve(puzzle)
    our_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in our_result.steps:
        if step.type in _ROW9_TYPES:
            our_elims.setdefault(step.type, []).extend(
                (c.index, c.value) for c in step.candidates_to_delete
            )

    assert technique in our_elims, (
        f"Our solver did not apply {technique.name} to this puzzle"
    )

    # Compare eliminations (sorted, so order doesn't matter)
    our_sorted = sorted(our_elims[technique])
    their_sorted = sorted(hodoku_elims[technique])
    assert our_sorted == their_sorted, (
        f"{technique.name} elimination mismatch:\n"
        f"  ours:   {our_sorted}\n"
        f"  HoDoKu: {their_sorted}"
    )
