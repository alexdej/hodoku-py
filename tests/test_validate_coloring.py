"""HoDoKu validation for Coloring: Simple Colors Trap/Wrap, Multi-Colors 1/2."""

from __future__ import annotations

import pytest

from hodoku_py.core.types import SolutionType
from hodoku_py.solver.solver import SudokuSolver
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
    # Simple Colors Wrap: TODO
    pytest.param(
        "simple_colors_wrap", "", SolutionType.SIMPLE_COLORS_WRAP,
        marks=pytest.mark.skip(reason="need a clean puzzle"),
    ),
    # Multi-Colors 1: 1 (r1c5,r4c3)/(r1c7,r2c4,r4c5),(r2c9,r6c7)/(r5c9) => r5c23<>1
    (
        "multi_colors_1",
        "000006000007030040106080095700900850900040020400008000093050010000007000000060002",
        SolutionType.MULTI_COLORS_1,
    ),
    # Multi-Colors 2: needs X-Wing/Finned X-Wing (row 13) before MC2 step
    pytest.param(
        "multi_colors_2",
        "100000040030000580590002000000000000050703600000000954070008060000460870003005000",
        SolutionType.MULTI_COLORS_2,
        marks=pytest.mark.skip(reason="dirty: requires X-Wing (row 13) to reach MC2 state"),
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
