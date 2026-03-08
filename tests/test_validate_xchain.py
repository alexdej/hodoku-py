"""HoDoKu validation for X-Chain."""

from __future__ import annotations

import pytest

from hodoku.core.types import SolutionType
from hodoku.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult

pytestmark = pytest.mark.hodoku

_XCHAIN_TYPES = frozenset({
    SolutionType.X_CHAIN,
})

XCHAIN_PUZZLES = [
    # X-Chain: 2 r5c4 =2= r6c6 -2- r6c2 =2= r9c2 -2- r7c3 =2= r7c9 => r5c9<>2
    # Clean: ssts before, singles after
    (
        "x_chain_1",
        "000000604000064000100800000078609050950003860000000007830095710000028000009000000",
        SolutionType.X_CHAIN,
    ),
]


@pytest.mark.parametrize("label,puzzle,technique", XCHAIN_PUZZLES)
def test_xchain_matches_hodoku(
    label: str, puzzle: str, technique: SolutionType, solve_with_hodoku
) -> None:
    hodoku: HodokuResult = solve_with_hodoku(puzzle)

    hodoku_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in hodoku.steps:
        if step.solution_type in _XCHAIN_TYPES:
            hodoku_elims.setdefault(step.solution_type, []).extend(step.eliminations)

    if technique not in hodoku_elims:
        pytest.skip(f"HoDoKu did not use {technique.name} on this puzzle")

    solver = SudokuSolver()
    our_result = solver.solve(puzzle)
    our_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in our_result.steps:
        if step.type in _XCHAIN_TYPES:
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
