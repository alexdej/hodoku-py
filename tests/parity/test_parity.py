"""Parity test suite — head-to-head comparison against HoDoKu.

Runs all puzzles from a puzzle file and compares our solver's solution path
step-for-step against HoDoKu's.  # comments become section labels in test IDs
and failure output.

Run (requires Java and --puzzle-file):
    pytest tests/parity/ --puzzle-file exemplars-1.0
    pytest tests/parity/ --puzzle-file top1465 --puzzle-count 50 -v
    pytest tests/parity/ --puzzle-file top1465 --puzzle-count 50 --puzzle-seed 7 -v
"""

from __future__ import annotations

import signal

import pytest

from hodoku.solver.solver import SudokuSolver
from tests.compare import first_divergence, hodoku_steps, our_steps, paths_match
from tests.parity.conftest import PuzzleEntry, HodokuResults, _load_puzzle_file, _resolve_puzzle_path

pytestmark = [pytest.mark.parity, pytest.mark.java]

SOLVE_TIMEOUT = 30  # seconds — puzzles exceeding this are marked FAILED


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "entry" not in metafunc.fixturenames:
        return
    puzzle_file = metafunc.config.getoption("--puzzle-file", default=None)
    if puzzle_file is None:
        return
    count = metafunc.config.getoption("--puzzle-count")
    seed = metafunc.config.getoption("--puzzle-seed")
    path = _resolve_puzzle_path(puzzle_file)
    entries = _load_puzzle_file(path, count, seed, file_stem=path.stem)
    metafunc.parametrize("entry", entries, ids=[e.test_id for e in entries])


def test_matches_hodoku(
    entry: PuzzleEntry,
    hodoku_parity_results: HodokuResults,
) -> None:
    """Our solver's solution path must match HoDoKu's step-for-step."""
    hodoku_result = hodoku_parity_results.get(entry.puzzle)
    if hodoku_result is None:
        pytest.skip("HoDoKu produced no result")
    if not hodoku_result.solved:
        pytest.skip("HoDoKu could not solve this puzzle")

    solver = SudokuSolver()

    def _timeout_handler(signum, frame):
        raise TimeoutError(f"Solver exceeded {SOLVE_TIMEOUT}s timeout")

    old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(SOLVE_TIMEOUT)
    try:
        our_result = solver.solve(entry.puzzle)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)

    ours = our_steps(our_result)
    theirs = hodoku_steps(hodoku_result)

    section_info = f"  section: {entry.section}\n" if entry.section else ""
    divergence = first_divergence(ours, theirs)
    assert paths_match(ours, theirs), (
        f"{section_info}"
        f"  puzzle: {entry.puzzle}\n"
        f"  ours ({len(ours)} steps) vs hodoku ({len(theirs)} steps)\n"
        f"{divergence}"
    )
