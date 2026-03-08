"""HoDoKu validation for finned/sashimi fish: Finned X-Wing, Finned Swordfish, Finned Jellyfish."""

from __future__ import annotations

import pytest

from hodoku.core.types import SolutionType
from hodoku.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult

pytestmark = pytest.mark.hodoku

_FINNED_TYPES = frozenset({
    SolutionType.FINNED_X_WING,
    SolutionType.FINNED_SWORDFISH,
    SolutionType.FINNED_JELLYFISH,
    SolutionType.SASHIMI_X_WING,
    SolutionType.SASHIMI_SWORDFISH,
    SolutionType.SASHIMI_JELLYFISH,
})

FINNED_FISH_PUZZLES = [
    # Finned X-Wing: 5 c47 r25 fr6c4 => r5c5<>5  (also has a second Finned X-Wing)
    (
        "finned_x_wing",
        "900000340000080070073600000060100980290000000010007200000060050100370000030900008",
        SolutionType.FINNED_X_WING,
    ),
    # Finned Swordfish: 3 r158 c257 fr1c8 => r3c7<>3
    (
        "finned_swordfish",
        "000400000300002805000087020050900001602100070000003000008000653701005000000000008",
        SolutionType.FINNED_SWORDFISH,
    ),
    # Finned Jellyfish: 3 c1459 r2567 fr9c4 fr9c5 => r7c6<>3
    (
        "finned_jellyfish",
        "270580000000900200000000036900705000040000000002000690100000000700809041600007908",
        SolutionType.FINNED_JELLYFISH,
    ),
]


@pytest.mark.parametrize("label,puzzle,technique", FINNED_FISH_PUZZLES)
def test_finned_fish_matches_hodoku(
    label: str, puzzle: str, technique: SolutionType, solve_with_hodoku
) -> None:
    hodoku: HodokuResult = solve_with_hodoku(puzzle)

    hodoku_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in hodoku.steps:
        if step.solution_type in _FINNED_TYPES:
            hodoku_elims.setdefault(step.solution_type, []).extend(step.eliminations)

    if technique not in hodoku_elims:
        pytest.skip(f"HoDoKu did not use {technique.name} on this puzzle")

    solver = SudokuSolver()
    our_result = solver.solve(puzzle)
    our_elims: dict[SolutionType, list[tuple[int, int]]] = {}
    for step in our_result.steps:
        if step.type in _FINNED_TYPES:
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
