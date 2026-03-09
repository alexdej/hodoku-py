"""HoDoKu validation for basic fish: X-Wing, Swordfish, Jellyfish."""

from __future__ import annotations

import pytest

from hodoku.core.types import SolutionType
from hodoku.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult

pytestmark = pytest.mark.java

_FISH_TYPES = frozenset({
    SolutionType.X_WING,
    SolutionType.SWORDFISH,
    SolutionType.JELLYFISH,
})

FISH_PUZZLES = [
    # X-Wing: 6 c67 r34 => r3c125,r4c5<>6
    (
        "x_wing",
        "000508237870402000000000000000000014506009020020001900008905070407600001090000000",
        SolutionType.X_WING,
    ),
    # Swordfish: 7 r369 c134 => r17c3,r2c14,r7c4<>7
    (
        "swordfish",
        "000501000063000000000080602680007040040000007020004560500000001000030078032010000",
        SolutionType.SWORDFISH,
    ),
    # Jellyfish: 2 r1359 c4678 => r4c68,r678c8,r7c67,r8c67<>2
    (
        "jellyfish",
        "009008000024790010000000095003000700500600003400017000030000000000470000001060059",
        SolutionType.JELLYFISH,
    ),
]


@pytest.mark.parametrize("label,puzzle,technique", FISH_PUZZLES)
def test_fish_matches_hodoku(
    label: str, puzzle: str, technique: SolutionType, solve_with_hodoku
) -> None:
    hodoku: HodokuResult = solve_with_hodoku(puzzle)

    hodoku_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in hodoku.steps:
        if step.solution_type in _FISH_TYPES:
            hodoku_elims.setdefault(step.solution_type, []).extend(step.eliminations)

    if technique not in hodoku_elims:
        pytest.skip(f"HoDoKu did not use {technique.name} on this puzzle")

    solver = SudokuSolver()
    our_result = solver.solve(puzzle)
    our_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in our_result.steps:
        if step.type in _FISH_TYPES:
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
