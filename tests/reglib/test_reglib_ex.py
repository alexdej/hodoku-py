"""End-to-end find_all_steps API test using reglib board states.

For each technique code in reglib-1.3.txt, takes the first usable entry
(non-fail, non-commented, known solution_types), reconstructs the exact PM
board state, calls Solver._find_all_on_grid(), and asserts the expected
technique appears somewhere in the results.

This exercises the find_all_steps filter loop (the all_steps_enabled gate and
technique dispatch) in a way that test_reglib.py does not — it calls targeted
finders directly, bypassing the API layer.

Run:
    pytest tests/reglib/test_reglib_ex.py -v
"""

from __future__ import annotations

import pytest

from hodoku import Solver
from hodoku.config import FishSearchConfig, FishType, SolverConfig, StepSearchConfig
from hodoku.core.grid import Grid
from hodoku.core.types import SolutionType as _ST
from tests.reglib.reglib_parser import ReglibEntry, parse_reglib, REGLIB_FILE

# Shared step overrides: enable templates for find-all
_STEP_OVERRIDES = {
    _ST.TEMPLATE_SET: dict(all_steps_enabled=True),
    _ST.TEMPLATE_DEL: dict(all_steps_enabled=True),
}

# Default config: Franken fish through jellyfish, ALS overlap off.
_DEFAULT_CONFIG = SolverConfig(
    find_all_search=StepSearchConfig(
        allow_duals_and_siamese=True,
        tabling_only_one_chain_per_elimination=False,
        tabling_allow_als_in_chains=True,
        als_allow_overlap=False,
        disabled_types=frozenset(),
    ),
    step_overrides=_STEP_OVERRIDES,
)

# Large/mutant fish config: mutant fish through whale.
_MUTANT_FISH_CONFIG = SolverConfig(
    find_all_search=StepSearchConfig(
        allow_duals_and_siamese=True,
        tabling_only_one_chain_per_elimination=False,
        tabling_allow_als_in_chains=True,
        als_allow_overlap=False,
        disabled_types=frozenset(),
        fish=FishSearchConfig(
            fish_type=FishType.BASIC_FRANKEN_MUTANT,
            max_size=7,
        ),
    ),
    step_overrides=_STEP_OVERRIDES,
)

# ALS overlap config: for Death Blossom.
_ALS_OVERLAP_CONFIG = SolverConfig(
    find_all_search=StepSearchConfig(
        allow_duals_and_siamese=True,
        tabling_only_one_chain_per_elimination=False,
        tabling_allow_als_in_chains=True,
        als_allow_overlap=True,
        disabled_types=frozenset(),
    ),
    step_overrides=_STEP_OVERRIDES,
)

# Technique codes that need a non-default config
_MUTANT_FISH_CODES = frozenset({"0332", "0342", "0362", "0363", "0364"})
_ALS_OVERLAP_CODES = frozenset({"0904"})

_CONFIG_FOR_CODE = {
    code: _MUTANT_FISH_CONFIG for code in _MUTANT_FISH_CODES
} | {
    code: _ALS_OVERLAP_CONFIG for code in _ALS_OVERLAP_CODES
}

# Pre-build solvers (one per config to reuse StepFinder caches)
_SOLVERS = {
    id(cfg): Solver(config=cfg)
    for cfg in (_DEFAULT_CONFIG, _MUTANT_FISH_CONFIG, _ALS_OVERLAP_CONFIG)
}


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
    config = _CONFIG_FOR_CODE.get(entry.technique_code, _DEFAULT_CONFIG)
    solver = _SOLVERS[id(config)]

    grid = _build_grid(entry)
    steps = solver._find_all_on_grid(grid)
    found_types = {s.type for s in steps}
    assert entry.solution_types & found_types, (
        f"Technique {entry.technique_code} not found in find_all_steps results.\n"
        f"  Expected one of: {entry.solution_types}\n"
        f"  Got types: {sorted(found_types, key=lambda t: t.name)}"
    )
