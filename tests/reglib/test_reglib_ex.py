"""End-to-end find_all_steps API test using reglib board states.

For each technique code in reglib-1.3.txt, takes the first usable entry
(non-fail, non-commented, known solution_types), reconstructs the exact PM
board state, calls Solver._find_all_on_grid(), and asserts the expected
technique appears somewhere in the results.

This exercises the find_all_steps filter loop (the all_steps_enabled gate and
technique dispatch) in a way that test_reglib.py does not — it calls targeted
finders directly, bypassing the API layer.

NOT wired into the default conftest collector.  Run explicitly:
    pytest tests/reglib/test_reglib_ex.py -v

Known failures (28 as of initial run) and their root causes
------------------------------------------------------------
These are the acceptance criteria for SolverConfig Pass 1 — all should pass
once find_all_search defaults are wired correctly.

| Codes          | Category                  | Root cause / fix needed                          |
|----------------|---------------------------|--------------------------------------------------|
| 0300–0364      | Fish (all types)          | all_steps_enabled=False bug; need search_fish    |
|                |                           | flag from FishSearchConfig to include fish        |
| 0404, 0405     | Dual Two-String Kite,     | allow_duals_and_siamese=False by default; Java   |
|                | Dual Empty Rectangle      | RegressionTester sets it True for these tests    |
| 0501, 0503     | Simple Colors Wrap,       | Alias types: find_all_steps dispatches to the    |
|                | Multi-Colors 2            | base type (TRAP/1), not the alias variant        |
| 0707, 0708,    | DNL, AIC, Grouped DNL,    | tabling_only_one_chain_per_elimination=True by   |
| 0710, 0711     | Grouped AIC               | default; find-all default should be False        |
| 0904           | Death Blossom             | als_allow_overlap variant interaction; needs     |
|                |                           | investigation when wiring ALS config             |
| 1201, 1202     | Template Set/Delete       | In disabled_types by default for find-all;       |
|                |                           | regression tester enables them explicitly        |
"""

from __future__ import annotations

import pytest

from hodoku import Solver
from hodoku.core.grid import Grid
from hodoku.core.types import SolutionType
from tests.reglib.reglib_parser import ReglibEntry, parse_reglib, REGLIB_FILE


def _build_grid(entry: ReglibEntry) -> Grid:
    grid = Grid()
    grid.set_sudoku(entry.givens_placed)
    for digit, row, col in entry.deleted_candidates:
        grid.del_candidate((row - 1) * 9 + (col - 1), digit)
    return grid


def _select_entries() -> list[ReglibEntry]:
    """One representative entry per technique code: first usable non-fail entry."""
    all_entries = parse_reglib(REGLIB_FILE)
    seen: set[str] = set()
    selected: list[ReglibEntry] = []
    for entry in all_entries:
        if entry.technique_code in seen:
            continue
        if entry.fail_case or entry.commented_out:
            continue
        if not entry.solution_types:
            continue
        seen.add(entry.technique_code)
        selected.append(entry)
    return selected


_ENTRIES = _select_entries()


@pytest.mark.parametrize(
    "entry",
    _ENTRIES,
    ids=[e.test_id for e in _ENTRIES],
)
def test_find_all_steps_contains_technique(entry: ReglibEntry) -> None:
    grid = _build_grid(entry)
    steps = Solver()._find_all_on_grid(grid)
    found_types = {s.type for s in steps}
    assert entry.solution_types & found_types, (
        f"Technique {entry.technique_code} not found in find_all_steps results.\n"
        f"  Expected one of: {entry.solution_types}\n"
        f"  Got types: {sorted(found_types, key=lambda t: t.name)}"
    )
