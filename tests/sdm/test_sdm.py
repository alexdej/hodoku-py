"""Broad-variety SDM regression suite.

Runs all puzzles from an .sdm file by default; use --sdm-count to sample a
subset. # comments become section labels in test IDs and failure output.
Commented-out puzzle lines (# followed by 81 digits/dots) are silently skipped.

Run (requires Java and --sdm-file):
    pytest tests/sdm/ --sdm-file top1465
    pytest tests/sdm/ --sdm-file sudocue_top10000 --sdm-count 100
    pytest tests/sdm/ --sdm-file top1465 --sdm-count 50 --sdm-seed 7 -v
"""

from __future__ import annotations

import pytest

from hodoku.solver.solver import SudokuSolver
from tests.compare import first_divergence, hodoku_path, solution_path
from tests.hodoku_harness import HodokuResult
from tests.sdm.conftest import SdmEntry, _load_sdm, _resolve_sdm_path

pytestmark = [pytest.mark.sdm, pytest.mark.hodoku]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "entry" not in metafunc.fixturenames:
        return
    sdm_file = metafunc.config.getoption("--sdm-file", default=None)
    if sdm_file is None:
        return
    count = metafunc.config.getoption("--sdm-count")
    seed = metafunc.config.getoption("--sdm-seed")
    path = _resolve_sdm_path(sdm_file)
    entries = _load_sdm(path, count, seed, file_stem=path.stem)
    metafunc.parametrize("entry", entries, ids=[e.test_id for e in entries])


def test_matches_hodoku(
    entry: SdmEntry,
    hodoku_sdm_results: dict[str, HodokuResult],
) -> None:
    """Our solver's solution path must match HoDoKu's step-for-step."""
    hodoku_result = hodoku_sdm_results.get(entry.puzzle)
    if hodoku_result is None:
        pytest.skip("HoDoKu produced no result")
    if not hodoku_result.solved:
        pytest.skip("HoDoKu could not solve this puzzle")

    solver = SudokuSolver()
    our_result = solver.solve(entry.puzzle)

    ours = solution_path(our_result)
    theirs = hodoku_path(hodoku_result)

    section_info = f"  section: {entry.section}\n" if entry.section else ""
    assert ours == theirs, (
        f"{section_info}"
        f"  puzzle: {entry.puzzle}\n"
        f"  ours ({len(ours)} steps) vs hodoku ({len(theirs)} steps)\n"
        f"{first_divergence(ours, theirs)}"
    )
