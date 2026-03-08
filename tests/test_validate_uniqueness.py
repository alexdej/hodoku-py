"""HoDoKu validation for Uniqueness techniques: UT1-6, BUG+1."""

from __future__ import annotations

import pytest

from hodoku.core.types import SolutionType
from hodoku.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult

pytestmark = pytest.mark.hodoku

_UT_TYPES = frozenset({
    SolutionType.UNIQUENESS_1,
    SolutionType.UNIQUENESS_2,
    SolutionType.UNIQUENESS_3,
    SolutionType.UNIQUENESS_4,
    SolutionType.UNIQUENESS_5,
    SolutionType.UNIQUENESS_6,
    SolutionType.HIDDEN_RECTANGLE,
    SolutionType.BUG_PLUS_1,
})

UNIQUENESS_PUZZLES = [
    # UT1: 4/9 in r5c1,r9c8 (two UT1 steps)
    (
        "ut1",
        "060000000000000700900005614000000000009502080005167003800000000400000832007031000",
        SolutionType.UNIQUENESS_1,
    ),
    # UT2: 1/8 in r4c59,r6c59 => r6c8,r9c9<>2
    (
        "ut2",
        "000900000070803006035100000000000390001020005000007400700000000060000509109408700",
        SolutionType.UNIQUENESS_2,
    ),
    # UT3: 1/2 in r2c45,r7c45 => r7c2<>6
    (
        "ut3",
        "000600000000000009659304020900000000000082010030060700003000800794000000002009050",
        SolutionType.UNIQUENESS_3,
    ),
    # UT4: 6/8 in r2c13,r4c13 => r2c13<>6
    (
        "ut4",
        "047230000000000000000080150000103540400000000500047009000500068063000000280060010",
        SolutionType.UNIQUENESS_4,
    ),
    # UT6: 5/7 in r1c68,r2c68 => r1c6,r2c8<>7
    (
        "ut6",
        "603010800000430000000000240260009708300060000705000000000008516800000097001000000",
        SolutionType.UNIQUENESS_6,
    ),
    # UT5: 2/9 in r2c19,r3c19 => r3c2<>7
    (
        "ut5",
        "450000008016000000000003400037200090000000001000600040000050800000070056800004300",
        SolutionType.UNIQUENESS_5,
    ),
    # Hidden Rectangle: 6/8 in r4c14,r6c14 => r4c1<>6
    (
        "hidden_rectangle",
        "017906000009050081080001300000009010000300908000000023900000700005100000740000000",
        SolutionType.HIDDEN_RECTANGLE,
    ),
    # BUG+1: trivalue cell r3c1; only digit 3 appears 3x in its row/col/box => r3c1<>1,9
    (
        "bug_plus_1",
        "000003047600000002070000800004001063000005009800739000000302000006000508730516200",
        SolutionType.BUG_PLUS_1,
    ),
]


@pytest.mark.parametrize("label,puzzle,technique", UNIQUENESS_PUZZLES)
def test_uniqueness_matches_hodoku(
    label: str, puzzle: str, technique: SolutionType, solve_with_hodoku
) -> None:
    hodoku: HodokuResult = solve_with_hodoku(puzzle)

    hodoku_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in hodoku.steps:
        if step.solution_type in _UT_TYPES:
            hodoku_elims.setdefault(step.solution_type, []).extend(step.eliminations)

    if technique not in hodoku_elims:
        pytest.skip(f"HoDoKu did not use {technique.name} on this puzzle")

    solver = SudokuSolver()
    our_result = solver.solve(puzzle)
    our_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in our_result.steps:
        if step.type in _UT_TYPES:
            our_elims.setdefault(step.type, []).extend(
                (c.index, c.value) for c in step.candidates_to_delete
            )

    assert technique in our_elims, (
        f"Our solver did not apply {technique.name} to this puzzle"
    )

    our_sorted = sorted(our_elims[technique])
    their_sorted = sorted(hodoku_elims[technique])
    assert our_sorted == their_sorted, (
        f"{technique.name} elimination mismatch:\n"
        f"  ours:   {our_sorted}\n"
        f"  HoDoKu: {their_sorted}"
    )
