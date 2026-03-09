"""pytest configuration for the reglib technique-isolation test suite.

Each entry in reglib-1.3.txt is a fully specified pencilmark state plus the
expected output of exactly one technique.  Unlike the exemplars regression
suite (which validates full solve paths against HoDoKu's CLI output), the
reglib tests are pure Python: no JVM, no HoDoKu binary needed.

Options
-------
  --reglib-section CODE   Run only entries whose technique code starts with CODE
                          (e.g. "0901" for ALS-XZ, "09" for all ALS).
  --reglib-count N        Limit to the first N entries (after section filter).

Running
-------
  pytest tests/reglib/ -v
  pytest tests/reglib/ --reglib-section 0901 -v
  pytest tests/reglib/ --reglib-section 09 --reglib-count 20 -v
"""

from __future__ import annotations

import pytest

from tests.reglib.reglib_parser import ReglibEntry, parse_reglib, REGLIB_FILE


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--reglib-section",
        default=None,
        help="Filter reglib entries to those whose technique code starts with this prefix.",
    )
    parser.addoption(
        "--reglib-count",
        type=int,
        default=None,
        help="Limit reglib run to the first N entries (after section filter).",
    )


def _load_entries(config: pytest.Config) -> list[ReglibEntry]:
    entries = parse_reglib(REGLIB_FILE)
    section = config.getoption("--reglib-section", default=None)
    if section:
        entries = [e for e in entries if e.technique_code.startswith(section)]
    count = config.getoption("--reglib-count", default=None)
    if count is not None:
        entries = entries[:count]
    return entries


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "reglib_entry" not in metafunc.fixturenames:
        return
    entries = _load_entries(metafunc.config)
    metafunc.parametrize("reglib_entry", entries, ids=[e.test_id for e in entries])
