"""Broad-variety SDM regression suite.

Samples puzzles from an .sdm file, runs both our solver and HoDoKu, and
compares solution paths step-for-step.

Run (requires Java and --sdm-file):
    pytest tests/sdm/ --sdm-file tests/testdata/top1465.sdm
    pytest tests/sdm/ --sdm-file tests/testdata/sudocue_top10000.sdm --sdm-count 100
    pytest tests/sdm/ --sdm-file tests/testdata/top1465.sdm --sdm-seed 7 -v
"""

from __future__ import annotations

import pytest

from hodoku.solver.solver import SudokuSolver
from tests.compare import first_divergence, hodoku_path, solution_path
from tests.hodoku_harness import HodokuResult

pytestmark = [pytest.mark.sdm, pytest.mark.hodoku]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "puzzle" not in metafunc.fixturenames:
        return
    sdm_file = metafunc.config.getoption("--sdm-file", default=None)
    if sdm_file is None:
        return
    # Puzzles are loaded by the sdm_puzzles session fixture; use indirect
    # parametrize so each puzzle becomes its own test item with a clean ID.
    count = metafunc.config.getoption("--sdm-count")
    seed = metafunc.config.getoption("--sdm-seed")

    import random
    from tests.sdm.conftest import _resolve_sdm_path
    path = _resolve_sdm_path(sdm_file)
    lines = path.read_text(encoding="utf-8").splitlines()
    puzzles = [ln.strip()[:81] for ln in lines if len(ln.strip()) >= 81]
    if len(puzzles) > count:
        rng = random.Random(seed)
        puzzles = rng.sample(puzzles, count)

    metafunc.parametrize("puzzle", puzzles, ids=[f"p{i}" for i in range(len(puzzles))])


def test_matches_hodoku(
    puzzle: str,
    hodoku_sdm_results: dict[str, HodokuResult],
) -> None:
    """Our solver's solution path must match HoDoKu's step-for-step."""
    hodoku_result = hodoku_sdm_results.get(puzzle)
    if hodoku_result is None:
        pytest.skip("HoDoKu produced no result")
    if not hodoku_result.solved:
        pytest.skip("HoDoKu could not solve this puzzle")

    solver = SudokuSolver()
    our_result = solver.solve(puzzle)

    ours = solution_path(our_result)
    theirs = hodoku_path(hodoku_result)

    assert ours == theirs, (
        f"  puzzle: {puzzle}\n"
        f"  ours ({len(ours)} steps) vs hodoku ({len(theirs)} steps)\n"
        f"{first_divergence(ours, theirs)}"
    )
