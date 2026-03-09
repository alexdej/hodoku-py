"""Exemplars regression suite.

Each puzzle from exemplars-1.0.txt becomes a single test that compares our
solver's solution path directly against HoDoKu's.  The exemplar file is used
only for grouping and test IDs — the ground truth is HoDoKu itself.

Run (default 10, requires Java):
    pytest tests/regression/ -v

Run more:
    pytest tests/regression/ --exemplar-count 50 -v

Restrict to a section:
    pytest tests/regression/ --exemplar-section 0100 --exemplar-count 1000 -v
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from hodoku.solver.solver import SudokuSolver
from tests.compare import first_divergence, hodoku_path, solution_path
from tests.hodoku_harness import HodokuResult
from tests.regression.exemplars_parser import ExemplarEntry, parse_exemplars

_KNOWN_FAILURES_FILE = Path(__file__).parent / "known_failures.txt"
_KNOWN_FAILURES: frozenset[str] = (
    frozenset(_KNOWN_FAILURES_FILE.read_text().splitlines())
    if _KNOWN_FAILURES_FILE.exists()
    else frozenset()
)

pytestmark = [pytest.mark.regression, pytest.mark.java]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "entry" not in metafunc.fixturenames:
        return
    count = metafunc.config.getoption("--exemplar-count")
    section = metafunc.config.getoption("--exemplar-section")

    entries = parse_exemplars()
    if section:
        entries = [e for e in entries if e.section_code == section]
    entries = entries[:count]

    metafunc.parametrize(
        "entry",
        entries,
        ids=[e.test_id for e in entries],
    )


# ---------------------------------------------------------------------------
# The test
# ---------------------------------------------------------------------------

def test_matches_hodoku(
    entry: ExemplarEntry,
    hodoku_exemplar_results: dict[str, HodokuResult],
) -> None:
    """Our solver's solution path must match HoDoKu's step-for-step."""
    hodoku_result = hodoku_exemplar_results.get(entry.puzzle)
    if hodoku_result is None:
        pytest.skip(f"HoDoKu produced no result for puzzle {entry.puzzle}")
    if not hodoku_result.solved:
        pytest.skip(f"HoDoKu could not solve puzzle {entry.puzzle}")

    solver = SudokuSolver()
    our_result = solver.solve(entry.puzzle)

    ours = solution_path(our_result)
    theirs = hodoku_path(hodoku_result)

    # Warn if the section's expected technique doesn't appear in HoDoKu's path.
    if entry.expected_types:
        hodoku_types = {t for t, _ in theirs}
        if not hodoku_types & entry.expected_types:
            warnings.warn(
                f"[{entry.section_code}: {entry.section_name}] line {entry.line_num}: "
                f"expected technique(s) {[t.name for t in entry.expected_types]} "
                f"not found in HoDoKu solution path",
                stacklevel=2,
            )

    try:
        assert ours == theirs, (
            f"[{entry.section_code}: {entry.section_name}] line {entry.line_num}\n"
            f"  puzzle: {entry.puzzle}\n"
            f"{first_divergence(ours, theirs)}"
        )
    except AssertionError:
        if entry.test_id in _KNOWN_FAILURES:
            pytest.xfail("listed in known_failures.txt")
        raise
