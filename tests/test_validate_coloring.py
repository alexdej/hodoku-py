"""HoDoKu validation for Coloring: Simple Colors Trap/Wrap, Multi-Colors 1/2."""

from __future__ import annotations

import pytest

from hodoku.core.types import SolutionType
from hodoku.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult

pytestmark = pytest.mark.hodoku

_COLORING_TYPES = frozenset({
    SolutionType.SIMPLE_COLORS_TRAP,
    SolutionType.SIMPLE_COLORS_WRAP,
    SolutionType.MULTI_COLORS_1,
    SolutionType.MULTI_COLORS_2,
})

COLORING_PUZZLES = [
    # Simple Colors Trap: 7 (r3c4,r6c2,r7c1)/(r5c1,r6c4,r7c5,r8c2) => r3c5<>7
    (
        "simple_colors_trap",
        "600280000207609580000000000100300000000000650400021090010005000008400023000000070",
        SolutionType.SIMPLE_COLORS_TRAP,
    ),
    # Simple Colors Wrap: 8 in r157 => r1c9,r2c14,r39c2,r4c4,r5c3,r6c7,r7c6,r9c5<>8
    (
        "simple_colors_wrap",
        "000000000000030605200105040000090300060700500010004002790600000500000981102000000",
        SolutionType.SIMPLE_COLORS_WRAP,
    ),
    # Multi-Colors 1: 1 (r1c5,r4c3)/(r1c7,r2c4,r4c5),(r2c9,r6c7)/(r5c9) => r5c23<>1
    (
        "multi_colors_1",
        "000006000007030040106080095700900850900040020400008000093050010000007000000060002",
        SolutionType.MULTI_COLORS_1,
    ),
    # Multi-Colors 2: 9 (r1c4,r8c7)/(r1c7,r2c6,r5c4,r9c9),(r6c5,r7c6)/(r9c5) => r1c7,r2c6,r5c4,r9c9<>9
    (
        "multi_colors_2",
        "450000008016000000000003400037200090000000001000600040000050800000070056800004300",
        SolutionType.MULTI_COLORS_2,
    ),
]


@pytest.mark.parametrize("label,puzzle,technique", COLORING_PUZZLES)
def test_coloring_matches_hodoku(
    label: str, puzzle: str, technique: SolutionType, solve_with_hodoku
) -> None:
    hodoku: HodokuResult = solve_with_hodoku(puzzle)

    hodoku_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in hodoku.steps:
        if step.solution_type in _COLORING_TYPES:
            hodoku_elims.setdefault(step.solution_type, []).extend(step.eliminations)

    if technique not in hodoku_elims:
        pytest.skip(f"HoDoKu did not use {technique.name} on this puzzle")

    solver = SudokuSolver()
    our_result = solver.solve(puzzle)
    our_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in our_result.steps:
        if step.type in _COLORING_TYPES:
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
