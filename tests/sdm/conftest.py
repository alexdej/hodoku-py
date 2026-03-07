"""pytest configuration for the SDM broad-variety test suite.

Provides:
  --sdm-file PATH    path to an .sdm file (required to run any tests)
  --sdm-count N      how many puzzles to sample (default: 20)
  --sdm-seed N       RNG seed for random sampling (default: 42)

Session fixtures:
  sdm_puzzles              the sampled puzzle strings
  hodoku_sdm_results       dict[puzzle, HodokuResult] — one JVM invocation
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from tests.hodoku_harness import HodokuResult, run_hodoku_batch

PROJECT_ROOT = Path(__file__).parent.parent.parent


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--sdm-file",
        default=None,
        help="Path to .sdm puzzle file to test (required for tests/sdm/).",
    )
    parser.addoption(
        "--sdm-count",
        type=int,
        default=20,
        help="Number of puzzles to sample from the .sdm file (default: 20).",
    )
    parser.addoption(
        "--sdm-seed",
        type=int,
        default=42,
        help="RNG seed for random sampling (default: 42).",
    )


def _load_sdm(path: Path, count: int, seed: int) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    puzzles = [ln.strip()[:81] for ln in lines if len(ln.strip()) >= 81]
    if len(puzzles) > count:
        rng = random.Random(seed)
        puzzles = rng.sample(puzzles, count)
    return puzzles


@pytest.fixture(scope="session")
def sdm_puzzles(request: pytest.FixtureRequest) -> list[str]:
    sdm_file = request.config.getoption("--sdm-file")
    if sdm_file is None:
        pytest.skip("--sdm-file not provided")
    count = request.config.getoption("--sdm-count")
    seed = request.config.getoption("--sdm-seed")
    path = Path(sdm_file)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        pytest.fail(f"--sdm-file not found: {path}")
    return _load_sdm(path, count, seed)


@pytest.fixture(scope="session")
def hodoku_sdm_results(
    sdm_puzzles: list[str],
    hodoku_available: bool,  # from parent conftest — skips if HoDoKu absent
) -> dict[str, HodokuResult]:
    """Run HoDoKu on all selected puzzles in one JVM invocation."""
    return run_hodoku_batch(sdm_puzzles)
