"""HoDoKu validation for ALS-XZ, ALS-XY-Wing, and ALS-XY-Chain."""

from __future__ import annotations

import pytest

from hodoku.core.types import SolutionType
from hodoku.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult

pytestmark = pytest.mark.hodoku

_ALS_TYPES = frozenset({
    SolutionType.ALS_XZ,
    SolutionType.ALS_XY_WING,
    SolutionType.ALS_XY_CHAIN,
})

# (label, puzzle, expected_technique)
ALS_PUZZLES = [
    # ALS-XZ + ALS-XY-Wing + ALS-Chain all appear; labelled by the first/primary technique.
    # From hodoku/als.txt (axz entry). All three ALS types fire in the solve path.
    (
        "als_xz_1",
        "....68.31.185.42......7..........7.5.5.3..........6.14..1..9.8394.........36...7.",
        SolutionType.ALS_XZ,
    ),
    # ALS-XY-Wing only (axy entry from hodoku/als.txt)
    (
        "als_xy_wing_1",
        ".847...9.....1.2.....56..346..25..............9....725.526....3....3.....6.8....9",
        SolutionType.ALS_XY_WING,
    ),
    # ALS-XZ (multiple) + ALS-Chain (ach entry from hodoku/als.txt)
    (
        "als_xy_chain_1",
        ".49.3.5.......5.7.....7.98...4.9235..5.1..........8.4..93............21..16...8..",
        SolutionType.ALS_XY_CHAIN,
    ),
]


@pytest.mark.parametrize("label,puzzle,technique", ALS_PUZZLES)
def test_als_matches_hodoku(
    label: str, puzzle: str, technique: SolutionType, solve_with_hodoku
) -> None:
    hodoku: HodokuResult = solve_with_hodoku(puzzle)

    hodoku_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in hodoku.steps:
        if step.solution_type in _ALS_TYPES:
            hodoku_elims.setdefault(step.solution_type, []).extend(step.eliminations)

    if technique not in hodoku_elims:
        pytest.skip(f"HoDoKu did not use {technique.name} on this puzzle")

    solver = SudokuSolver()
    our_result = solver.solve(puzzle)
    our_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in our_result.steps:
        if step.type in _ALS_TYPES:
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
