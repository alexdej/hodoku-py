"""HoDoKu validation for AIC, Continuous Nice Loop, Discontinuous Nice Loop."""

from __future__ import annotations

import pytest

from hodoku_py.core.types import SolutionType
from hodoku_py.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult

pytestmark = pytest.mark.hodoku

_AIC_TYPES = frozenset({
    SolutionType.AIC,
    SolutionType.CONTINUOUS_NICE_LOOP,
    SolutionType.DISCONTINUOUS_NICE_LOOP,
})

AIC_PUZZLES = [
    # AIC: 5 5- r1c4 =5= r3c6 =8= r3c5 =9= r6c5 =3= r6c1 -3- r3c1 -5 => r1c13,r3c6<>5
    # Clean: ssts before, ssts after (single AIC, all surrounding techniques implemented)
    (
        "aic_1",
        "060003098000070305010200007000000030900002400048000000000050001600000000290000003",
        SolutionType.AIC,
    ),
    # Continuous Nice Loop: 2/3/6/8 5= r7c6 =2= r6c6 ... => r46c4,r6c5<>2, r26c5<>3, r7c6<>6, r78c6<>8
    # Clean: singles before, singles after
    (
        "continuous_nice_loop_1",
        "000060100027500006000004308400007980000050201000000000004000000061900024030001000",
        SolutionType.CONTINUOUS_NICE_LOOP,
    ),
    # Continuous Nice Loop: 3/4/6/7 7= r5c9 =6= r5c8 ... => r5c9<>3, r2c4<>4, r9c8<>6, r1c3,r4c6<>7
    # Clean: ssts (incl. HR, ER) before, ssts after
    (
        "continuous_nice_loop_2",
        "000008010900030070540029600006800590000000000000000842600000000008970001070041000",
        SolutionType.CONTINUOUS_NICE_LOOP,
    ),
    # Discontinuous Nice Loop: 6/7/8/9 r8c2 =4= r8c9 -4- r9c9 -2- r9c3 =2= r7c2 =4= r8c2 => r8c2<>6,7,8,9
    # Clean: ssts before, singles after
    (
        "discontinuous_nice_loop_1",
        "007065000010008436400000000000600003004020001000040200001000007000002000530070910",
        SolutionType.DISCONTINUOUS_NICE_LOOP,
    ),
    # Discontinuous Nice Loop: 3 r4c3 -3- r6c2 -7- r3c2 =7= r3c3 =8= r4c3 => r4c3<>3
    # Clean: ssts (X-Wing) before, AIC after
    (
        "discontinuous_nice_loop_2",
        "001067300020093578300000000010900000000000087004056900000000000080000029000002050",
        SolutionType.DISCONTINUOUS_NICE_LOOP,
    ),
]


@pytest.mark.parametrize("label,puzzle,technique", AIC_PUZZLES)
def test_aic_matches_hodoku(
    label: str, puzzle: str, technique: SolutionType, solve_with_hodoku
) -> None:
    hodoku: HodokuResult = solve_with_hodoku(puzzle)

    hodoku_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in hodoku.steps:
        if step.solution_type in _AIC_TYPES:
            hodoku_elims.setdefault(step.solution_type, []).extend(step.eliminations)

    if technique not in hodoku_elims:
        pytest.skip(f"HoDoKu did not use {technique.name} on this puzzle")

    solver = SudokuSolver()
    our_result = solver.solve(puzzle)
    our_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in our_result.steps:
        if step.type in _AIC_TYPES:
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
