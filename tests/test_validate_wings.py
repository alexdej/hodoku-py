"""HoDoKu validation for Wing patterns: W-Wing, XY-Wing, XYZ-Wing."""

from __future__ import annotations

import pytest

from hodoku_py.core.types import SolutionType
from hodoku_py.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult

pytestmark = pytest.mark.hodoku

_WING_TYPES = frozenset({
    SolutionType.W_WING,
    SolutionType.XY_WING,
    SolutionType.XYZ_WING,
})

WING_PUZZLES = [
    # W-Wing: 2/6 in r1c5,r3c8 connected by 6 in r2c48 => r1c8<>2
    (
        "w_wing",
        "901800000030005000000390100000170630082050000000000000000000970700030041106002005",
        SolutionType.W_WING,
    ),
    # XY-Wing: 1/2/3 in r2c7,r3c18 => r3c7<>3
    (
        "xy_wing",
        "008200570705400008009857000451729863276583941983614752692345187537168000814972635",
        SolutionType.XY_WING,
    ),
    # XYZ-Wing: 1/3/5 in r3c13,r6c3 => r1c3<>5  (also has XY-Wing before it, both implemented)
    (
        "xyz_wing",
        "000000000000637002000000867200008000000000950000064083802400000147203000009800000",
        SolutionType.XYZ_WING,
    ),
]


@pytest.mark.parametrize("label,puzzle,technique", WING_PUZZLES)
def test_wing_matches_hodoku(
    label: str, puzzle: str, technique: SolutionType, solve_with_hodoku
) -> None:
    hodoku: HodokuResult = solve_with_hodoku(puzzle)

    hodoku_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in hodoku.steps:
        if step.solution_type in _WING_TYPES:
            hodoku_elims.setdefault(step.solution_type, []).extend(step.eliminations)

    if technique not in hodoku_elims:
        pytest.skip(f"HoDoKu did not use {technique.name} on this puzzle")

    solver = SudokuSolver()
    our_result = solver.solve(puzzle)
    our_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in our_result.steps:
        if step.type in _WING_TYPES:
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
