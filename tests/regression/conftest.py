"""pytest configuration for the exemplars regression suite.

Provides:
  --exemplar-count N   how many exemplar entries to test (default 10)
  --exemplar-section S restrict to a single section code, e.g. "0100"

Session fixtures:
  exemplar_entries     the selected ExemplarEntry objects
  hodoku_exemplar_results   dict[puzzle, HodokuResult] — one JVM invocation
"""

from __future__ import annotations

import pytest

from tests.hodoku_harness import run_hodoku_batch, HodokuResult
from tests.regression.exemplars_parser import parse_exemplars, ExemplarEntry


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--exemplar-count",
        type=int,
        default=10,
        help="Number of exemplar entries to include in the regression run (default 10).",
    )
    parser.addoption(
        "--exemplar-section",
        default=None,
        help="Restrict regression run to a single section code, e.g. '0100'.",
    )


@pytest.fixture(scope="session")
def exemplar_entries(request: pytest.FixtureRequest) -> list[ExemplarEntry]:
    """Load and filter exemplar entries according to CLI options."""
    count = request.config.getoption("--exemplar-count")
    section = request.config.getoption("--exemplar-section")

    entries = parse_exemplars()
    if section:
        entries = [e for e in entries if e.section_code == section]
    return entries[:count]


@pytest.fixture(scope="session")
def hodoku_exemplar_results(
    exemplar_entries: list[ExemplarEntry],
    hodoku_available: bool,  # from parent conftest — skips if HoDoKu absent
) -> dict[str, HodokuResult]:
    """Run HoDoKu on all selected exemplar puzzles in one JVM invocation."""
    puzzles = [e.puzzle for e in exemplar_entries]
    return run_hodoku_batch(puzzles)
