"""Step-by-step validation of Locked Candidates and Naked/Hidden Subsets."""

from __future__ import annotations

import pytest

from hodoku.core.types import SolutionType
from hodoku.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult

pytestmark = pytest.mark.java

# Techniques covered by row 8
_ROW8_TYPES = frozenset({
    SolutionType.FULL_HOUSE,
    SolutionType.NAKED_SINGLE,
    SolutionType.HIDDEN_SINGLE,
    SolutionType.LOCKED_CANDIDATES_1,
    SolutionType.LOCKED_CANDIDATES_2,
    SolutionType.LOCKED_PAIR,
    SolutionType.NAKED_PAIR,
    SolutionType.LOCKED_TRIPLE,
    SolutionType.NAKED_TRIPLE,
    SolutionType.NAKED_QUADRUPLE,
    SolutionType.HIDDEN_PAIR,
    SolutionType.HIDDEN_TRIPLE,
    SolutionType.HIDDEN_QUADRUPLE,
})

# Puzzles that HoDoKu solves using only singles + subsets/LC
MEDIUM_PUZZLES = [
    # Needs Locked Candidates 1
    "000000000904607000076804100309701080008000300050308702007502610000403208000000000",
    # Needs Locked Pair, Naked Pair, Naked Triple, Locked Candidates 1
    "300200000000107000706030500070009080900020004010800050009040301000702000000008006",
]


@pytest.mark.parametrize("puzzle", MEDIUM_PUZZLES)
def test_subsets_match_hodoku(puzzle: str, solve_with_hodoku) -> None:
    hodoku: HodokuResult = solve_with_hodoku(puzzle)
    if not hodoku.solved:
        pytest.skip(f"HoDoKu could not solve puzzle (needs techniques beyond row 8): {puzzle}")

    hodoku_steps = [s for s in hodoku.steps if s.solution_type in _ROW8_TYPES]

    # If HoDoKu used techniques we haven't implemented, skip gracefully
    unknown = [s for s in hodoku.steps if s.solution_type not in _ROW8_TYPES]
    if unknown:
        pytest.skip(
            f"Puzzle needs unimplemented techniques: "
            f"{[s.solution_type for s in unknown]}"
        )

    solver = SudokuSolver()
    our_result = solver.solve(puzzle)
    assert our_result.solved, "Our solver could not solve the puzzle"

    assert len(our_result.steps) == len(hodoku_steps), (
        f"Step count mismatch: ours={len(our_result.steps)} hodoku={len(hodoku_steps)}\n"
        f"Ours:   {[s.type.name for s in our_result.steps]}\n"
        f"HoDoKu: {[s.solution_type.name for s in hodoku_steps]}"
    )

    _PLACEMENT = {SolutionType.FULL_HOUSE, SolutionType.NAKED_SINGLE, SolutionType.HIDDEN_SINGLE}

    for i, (ours, theirs) in enumerate(zip(our_result.steps, hodoku_steps)):
        assert ours.type == theirs.solution_type, (
            f"Step {i}: type mismatch ours={ours.type.name} theirs={theirs.solution_type}"
        )
        if ours.type in _PLACEMENT:
            assert ours.indices == theirs.indices, (
                f"Step {i} ({ours.type.name}): cell mismatch "
                f"ours={ours.indices} theirs={theirs.indices}"
            )
            assert ours.values == theirs.values, (
                f"Step {i} ({ours.type.name}): value mismatch "
                f"ours={ours.values} theirs={theirs.values}"
            )
        else:
            our_elims = sorted((c.index, c.value) for c in ours.candidates_to_delete)
            their_elims = sorted(theirs.eliminations)
            assert our_elims == their_elims, (
                f"Step {i} ({ours.type.name}): elimination mismatch "
                f"ours={our_elims} theirs={their_elims}"
            )
