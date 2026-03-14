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

import json
import sys

import pytest

from hodoku.solver.solver import SudokuSolver
from tests.compare import first_divergence, hodoku_steps, our_steps, paths_match, steps_match
from tests.parity.conftest import PuzzleEntry, HodokuResults, _load_puzzle_file, _resolve_puzzle_path

pytestmark = [pytest.mark.parity, pytest.mark.java]


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
    record_property,
    request: pytest.FixtureRequest,
) -> None:
    """Our solver's solution path must match HoDoKu's step-for-step."""
    record_property("puzzle", entry.puzzle)
    record_property("section", entry.section or "")
    hodoku_result = hodoku_parity_results.get(entry.puzzle)
    if hodoku_result is None:
        pytest.skip("HoDoKu produced no result")
    if not hodoku_result.solved:
        pytest.skip("HoDoKu could not solve this puzzle")

    record_property("hodoku_level", hodoku_result.level.value)
    record_property("hodoku_score", str(hodoku_result.score))
    record_property("hodoku_level_name", hodoku_result.level.name)

    solver = SudokuSolver()
    puzzle_timeout = request.config.getoption("--puzzle-timeout")

    if sys.platform != "win32":
        import signal

        def _timeout_handler(signum, frame):
            raise TimeoutError(f"Solver exceeded {puzzle_timeout}s timeout")

        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(puzzle_timeout)
        try:
            our_result = solver.solve(entry.puzzle)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        our_result = solver.solve(entry.puzzle)

    ours = our_steps(our_result)
    theirs = hodoku_steps(hodoku_result)

    record_property("ours_steps", str(len(ours)))
    record_property("hodoku_steps", str(len(theirs)))
    record_property("ours_score", str(our_result.score))
    record_property("ours_level", our_result.level.name)

    match = paths_match(ours, theirs)
    if not match:
        for i, (o, t) in enumerate(zip(ours, theirs)):
            if not steps_match(o, t):
                record_property("divergence", json.dumps({
                    "step": i + 1,
                    "ours":   {"type": o.type.value if o.type else None, "elims": list(o.eliminations), "placements": list(o.placements)},
                    "hodoku": {"type": t.type.value if t.type else None, "elims": list(t.eliminations), "placements": list(t.placements)},
                }))
                break

    section_info = f"  section: {entry.section}\n" if entry.section else ""
    divergence = first_divergence(ours, theirs)
    assert match, (
        f"{section_info}"
        f"  puzzle: {entry.puzzle}\n"
        f"  ours ({len(ours)} steps) vs hodoku ({len(theirs)} steps)\n"
        f"{divergence}"
    )

    assert our_result.score == hodoku_result.score, (
        f"{section_info}"
        f"  puzzle: {entry.puzzle}\n"
        f"  score: ours={our_result.score} hodoku={hodoku_result.score}"
    )
    assert our_result.level == hodoku_result.level, (
        f"{section_info}"
        f"  puzzle: {entry.puzzle}\n"
        f"  level: ours={our_result.level.name} hodoku={hodoku_result.level.name}"
    )
