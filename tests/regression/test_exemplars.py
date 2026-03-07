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

import pytest

from hodoku_py.core.types import SolutionType
from hodoku_py.solver.solver import SudokuSolver
from tests.hodoku_harness import HodokuResult
from tests.regression.exemplars_parser import ExemplarEntry, parse_exemplars

pytestmark = [pytest.mark.regression, pytest.mark.hodoku]


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
# Helpers
# ---------------------------------------------------------------------------

def _solution_path(solver_result) -> list[tuple[SolutionType, tuple]]:
    """Convert our solve result to a comparable list of (type, outcome) tuples."""
    path = []
    for step in solver_result.steps:
        if step.candidates_to_delete:
            outcome = tuple(sorted((c.index, c.value) for c in step.candidates_to_delete))
        else:
            outcome = tuple(sorted(zip(step.indices, step.values)))
        path.append((step.type, outcome))
    return path


def _hodoku_path(hodoku_result: HodokuResult) -> list[tuple[SolutionType | None, tuple]]:
    """Convert a HodokuResult to the same comparable form."""
    path = []
    for step in hodoku_result.steps:
        if step.eliminations:
            outcome = tuple(sorted(step.eliminations))
        else:
            outcome = tuple(sorted((idx, val) for idx, val in zip(step.indices, step.values)))
        path.append((step.solution_type, outcome))
    return path


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

    ours = _solution_path(our_result)
    theirs = _hodoku_path(hodoku_result)

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

    assert ours == theirs, (
        f"[{entry.section_code}: {entry.section_name}] line {entry.line_num}\n"
        f"  puzzle: {entry.puzzle}\n"
        f"  ours ({len(ours)} steps):   {ours}\n"
        f"  HoDoKu ({len(theirs)} steps): {theirs}"
    )
