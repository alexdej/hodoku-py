"""HoDoKu validation for XY-Chain and Remote Pair."""

from __future__ import annotations

import pytest

from hodoku.core.types import SolutionType
from hodoku.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult

pytestmark = pytest.mark.java

_XYCHAIN_TYPES = frozenset({
    SolutionType.XY_CHAIN,
    SolutionType.REMOTE_PAIR,
})

XYCHAIN_PUZZLES = [
    # XY-Chain: 6 6- r4c6 -3- r7c6 -6- r7c7 -9- r7c5 -7- r7c3 -1- r1c3 -2- r1c1 -1- r4c1 -7- r6c1 -8- r6c2 -6
    #   => r4c23,r6c4<>6
    # Clean: ssts before, singles after
    (
        "xy_chain_1",
        "070809406008000000543107800000000000000900067004051003000200080000005000000018302",
        SolutionType.XY_CHAIN,
    ),
    # XY-Chain: 3 3- r2c9 -4- r2c5 -8- r4c5 -3- r6c5 -1- r6c4 -6- r6c8 -3 => r12c8,r5c9<>3
    # Clean: ssts before, singles after
    (
        "xy_chain_2",
        "000000000100506200000003698001000000400090050257000000000070940002961000000008302",
        SolutionType.XY_CHAIN,
    ),
    # Remote Pair: 1/6 r3c2 -6- r3c9 -1- r1c7 -6- r6c7 => r6c2<>1, r6c2<>6
    # Clean: singles before, singles after
    (
        "remote_pair_1",
        "050390000800000500300720040000046703000007200500000000006003028480009000001000000",
        SolutionType.REMOTE_PAIR,
    ),
]


@pytest.mark.parametrize("label,puzzle,technique", XYCHAIN_PUZZLES)
def test_xychain_matches_hodoku(
    label: str, puzzle: str, technique: SolutionType, solve_with_hodoku
) -> None:
    hodoku: HodokuResult = solve_with_hodoku(puzzle)

    hodoku_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in hodoku.steps:
        if step.solution_type in _XYCHAIN_TYPES:
            hodoku_elims.setdefault(step.solution_type, []).extend(step.eliminations)

    if technique not in hodoku_elims:
        pytest.skip(f"HoDoKu did not use {technique.name} on this puzzle")

    solver = SudokuSolver()
    our_result = solver.solve(puzzle)
    our_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in our_result.steps:
        if step.type in _XYCHAIN_TYPES:
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
