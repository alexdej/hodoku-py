# Spec: SolverConfig

Top-level configuration object passed to `Solver`.  Replaces the module-level
constants in `scoring.py` (`DEFAULT_STEPS`, `SOLVER_STEPS`, `STEP_CONFIG`,
`DIFFICULTY_MAX_SCORE`) and unifies all solver tuning in one place.

---

## Class hierarchy

```
SolverConfig
├── solve_search: StepSearchConfig      # solve(), get_hint(), rate()
├── find_all_search: StepSearchConfig   # find_all_steps()
├── step_overrides: dict[SolutionType, dict]
└── difficulty_thresholds: dict[DifficultyType, int]

StepSearchConfig
├── fish: FishSearchConfig
├── kraken_fish: KrakenFishSearchConfig
├── chain_max_length: int
├── nice_loop_max_length: int
├── chain_restrict_length: bool
├── tabling_entry_size: int
├── tabling_net_depth: int
├── tabling_only_one_chain_per_elimination: bool
├── tabling_allow_als_in_chains: bool
├── als_allow_overlap: bool
├── als_only_one_per_elimination: bool
├── als_chain_length: int               # find-all only
├── als_chain_forward_only: bool        # find-all only
├── allow_ers_with_two_candidates: bool
├── allow_duals_and_siamese: bool
├── allow_missing_candidates_in_urs: bool
└── disabled_types: frozenset[SolutionType]  # find-all only

FishSearchConfig
├── search_fish: bool
├── fish_type: FishType
├── min_size: int
├── max_size: int
├── max_fins: int
├── max_endo_fins: int
├── check_templates: bool               # not applicable to kraken (hardcoded off)
├── only_one_per_elimination: bool      # not applicable to kraken
└── candidates: int                     # 9-bit mask

KrakenFishSearchConfig
├── search_kraken_fish: bool
├── fish_type: FishType
├── min_size: int
├── max_size: int
├── max_fins: int
├── max_endo_fins: int
└── candidates: int                     # 9-bit mask
```

`FishSearchConfig` and `KrakenFishSearchConfig` are two separate flat
dataclasses — no inheritance.  The repeated fields are intentional; there is
no polymorphic usage that would justify a base class.

---

## Proposed API

```python
from hodoku import Solver, SolverConfig

# All defaults — identical to current hardcoded behaviour
solver = Solver()

# Custom
cfg = SolverConfig(
    step_overrides={SolutionType.X_WING: dict(base_score=200)},
    difficulty_thresholds={DifficultyType.HARD: 2000},
)
solver = Solver(config=cfg)

# Access the search configs directly
cfg.solve_search.fish.max_fins        # 5
cfg.find_all_search.fish.max_fins     # 5
cfg.find_all_search.als_allow_overlap # True  (more permissive than solve)
```

`SolverConfig.DEFAULT` is a module-level singleton used when `Solver()` is
called with no arguments.

---

## FishType enum

```python
class FishType(enum.IntEnum):
    BASIC                = 0
    BASIC_FRANKEN        = 1   # default
    BASIC_FRANKEN_MUTANT = 2
```

---

## Helpers

```python
def make_candidates(digits: list[int]) -> int:
    """Build a 9-bit candidate mask from a list of digits 1–9.

    Examples:
        make_candidates([1, 2, 3])  # 0b000000111 = 7
        make_candidates(range(1, 10))  # 0x1FF — all digits
    """
    return sum(1 << (d - 1) for d in digits)
```

Lives in `hodoku/config.py` (or wherever the config classes land).

---

## Default values

### StepSearchConfig — solve defaults vs find-all defaults

Fields where the two contexts differ:

| Field | Solve default | Find-all default | Notes |
|---|---|---|---|
| `tabling_allow_als_in_chains` | `False` | `True` | Java: `allowAlsInTablingChains` vs `allStepsAllowAlsInTablingChains` |
| `tabling_only_one_chain_per_elimination` | `True` | `False` | Find-all wants all chains per elimination |
| `als_allow_overlap` | `False` | `True` | Java: `allowAlsOverlap` vs `allStepsAllowAlsOverlap` |
| `als_only_one_per_elimination` | `True` | `False` | Find-all wants all ALS steps per elimination |
| `als_chain_length` | n/a | `6` | Solve loop doesn't use this; range 4–7 |
| `als_chain_forward_only` | n/a | `True` | Solve loop doesn't use this |
| `disabled_types` | n/a | See below | Solve loop doesn't use this |

All other fields have the same default in both contexts:

| Field | Default | Java field | Notes |
|---|---|---|---|
| `chain_max_length` | `20` | `restrictChainLength` / `allStepsMaxChainLength` | X-chains, XY-chains, AICs |
| `nice_loop_max_length` | `10` | `restrictNiceLoopLength` | Nice loops only; separate limit from `chain_max_length` |
| `chain_restrict_length` | `True` | `restrictChainLength > 0` | Whether chain length limits are enforced |
| `tabling_entry_size` | `1000` | `maxTableEntryLength` | Max chain length allocated per table entry |
| `tabling_net_depth` | `4` | `anzTableLookAhead` | How many look-ahead expansion passes for forcing nets |
| `allow_ers_with_two_candidates` | `False` | `allowErsWithOnlyTwoCandidates` | |
| `allow_duals_and_siamese` | `False` | `allowDualsAndSiamese` | |
| `allow_missing_candidates_in_urs` | `False` | `allowMissingCandidatesInUr` | |

### FishSearchConfig defaults

| Field | Default | Java field |
|---|---|---|
| `search_fish` | `True` | `allStepsSearchFish` |
| `fish_type` | `FishType.BASIC_FRANKEN` | `maxFins` / `allStepsMaxFishType` |
| `min_size` | `2` | `allStepsMinFishSize`; range 2–7 |
| `max_size` | `4` | `allStepsMaxFishSize`; range 2–7 |
| `max_fins` | `5` | `maxFins` / `allStepsMaxFins`; range 0–10 |
| `max_endo_fins` | `2` | `maxEndoFins` / `allStepsMaxEndoFins`; range 0–10 |
| `check_templates` | `True` | `checkTemplates` / `allStepsCheckTemplates` |
| `only_one_per_elimination` | `True` | `onlyOneFishPerStep`; solve loop only — absent from find-all fish panel |
| `candidates` | `0x1FF` | 9-bit mask; find-all only — absent from Fish General panel; use `make_candidates([1,3,5])` to build |

### KrakenFishSearchConfig defaults

| Field | Default | Java field |
|---|---|---|
| `search_kraken_fish` | `False` | `allStepsEnabled` on `KRAKEN_FISH` |
| `fish_type` | `FishType.BASIC_FRANKEN` | `allStepsKrakenMaxFishType` |
| `min_size` | `2` | `allStepsKrakenMinFishSize`; range 2–7; **find-all only in Java** (solve loop has only `krakenMaxFishSize`) — present on both configs for symmetry, ignored in solve context |
| `max_size` | `4` | `allStepsKrakenMaxFishSize` / `krakenMaxFishSize`; range 2–7 |
| `max_fins` | `2` | `allStepsMaxKrakenFins`; range 0–10 |
| `max_endo_fins` | `0` | `allStepsMaxKrakenEndoFins`; range 0–10 |
| `candidates` | `0x1FF` | `allStepsKrakenFishCandidates`; 9-bit mask; use `make_candidates([1,3,5])` to build |

Note: `check_templates` is hardcoded to `False` inside `FishSolver` for kraken
searches (saved/restored around the call) — it is not a configurable field.

### disabled_types default (find-all only)

Last Resort techniques are unchecked by default in HoDoKu:
`KRAKEN_FISH_TYPE_1`, `KRAKEN_FISH_TYPE_2`, `FORCING_CHAIN_CONTRADICTION`,
`FORCING_CHAIN_VERITY`, `FORCING_NET_CONTRADICTION`, `FORCING_NET_VERITY`,
`TEMPLATE_SET`, `TEMPLATE_DEL`.

Fish types are absent — controlled by `FishSearchConfig.search_fish`.

### difficulty_thresholds defaults

| Level | Max score |
|---|---|
| `EASY` | 800 |
| `MEDIUM` | 1000 |
| `HARD` | 1600 |
| `UNFAIR` | 1800 |
| `EXTREME` | unbounded (`2**31 - 1`) |

### step_overrides default

Empty — `DEFAULT_STEPS` in `scoring.py` is used as-is.

---

## Integration points

| Location | Current usage | Change |
|---|---|---|
| `solver/solver.py` `SudokuSolver.solve()` | `SOLVER_STEPS`, `STEP_CONFIG`, `DIFFICULTY_MAX_SCORE` | Use `config.solver_steps`, `config.step_config`, `config.difficulty_thresholds` |
| `solver/solver.py` `_find_next_step()` | `SOLVER_STEPS` | Use `config.solver_steps` |
| `api.py` `Solver.get_hint()` | `SOLVER_STEPS` | Use `config.solver_steps` |
| `api.py` `Solver.find_all_steps()` | `SOLVER_STEPS` | Use `config.solver_steps` + `config.find_all_search` |
| `generator/generator.py` | `DIFFICULTY_MAX_SCORE` | Accept `SolverConfig` or pass thresholds directly |

`SolverConfig` exposes two derived read-only properties:
- `solver_steps: tuple[StepConfig, ...]` — enabled steps sorted by index
- `step_config: dict[SolutionType, StepConfig]` — fast lookup incl. aliases

Both are computed once at construction and cached.

---

## Implementation notes

- All config objects are frozen dataclasses.
- `DEFAULT_STEPS`, `SOLVER_STEPS`, `STEP_CONFIG`, `DIFFICULTY_MAX_SCORE`
  remain in `scoring.py` as the authoritative source that `SolverConfig()`
  with no args delegates to — they are not removed.
- The `STEP_CONFIG` alias entries (e.g. `SIMPLE_COLORS_WRAP` →
  `SIMPLE_COLORS_TRAP`) are reproduced in `SolverConfig.step_config` after
  applying any `step_overrides`.
- `allow_duals_and_siamese`: `fish.py`'s `_apply_siamese` is currently always
  active — it must be gated on this flag (default `False`).
- **find_all_search vs solve_search**: HoDoKu's "All possible steps" UI panel
  omits Chains, Tabling, and ALS sections, but that is a UI simplification —
  the underlying solvers accept the same parameters either way.  All
  `StepSearchConfig` fields apply in both contexts; fields with different
  solve vs find-all defaults are listed in the table above.
- **Regression constraint**: `SolverConfig()` with no arguments must produce
  identical solve paths to the current hardcoded behaviour.  Run the full
  reglib suite before merging.
