# hodoku-py Roadmap

Tracks implementation progress and what comes next.
Each layer depends only on those above it in the list.

---

## Status key

| Symbol | Meaning |
|--------|---------|
| ✅ | Done and validated against HoDoKu |
| 🔧 | In progress |
| ⬜ | Not started |

---

## Foundation

| # | Layer | File(s) | Status | Notes |
|---|-------|---------|--------|-------|
| 1 | Core types | `core/types.py` | ✅ | `SolutionType`, `SolutionCategory`, `DifficultyType` enums |
| 2 | Solution step | `core/solution_step.py` | ✅ | `SolutionStep`, `Candidate`, `Entity` dataclasses |
| 3 | Grid | `core/grid.py` | ✅ | 81-cell state, `free[][]`, `ns_queue`, `hs_queue`, static lookup tables |
| 4 | Scoring | `core/scoring.py` | ✅ | `StepConfig` table (90 entries), `SOLVER_STEPS`, difficulty thresholds |
| 5 | Solver loop | `solver/solver.py` | ✅ | `SudokuSolver.solve()`, SOLVER_STEPS priority loop, scoring |
| 6 | Step finder | `solver/step_finder.py` | ✅ | Dispatcher skeleton; grows as solvers are added |

## Solver techniques

| # | Layer | File | Status | Techniques |
|---|-------|------|--------|------------|
| 7 | Singles | `solver/simple.py` | ✅ | Full House, Naked Single, Hidden Single |
| 8 | Intersections + Subsets | `solver/simple.py` | ✅ | Locked Candidates 1&2, Naked/Hidden Pair/Triple/Quad, Locked Pair/Triple |
| 9 | Single-digit patterns | `solver/single_digit.py` | ✅ | Skyscraper, 2-String Kite, Empty Rectangle |
| 10 | Wings | `solver/wings.py` | ✅ | W-Wing, XY-Wing, XYZ-Wing |
| 11 | Coloring | `solver/coloring.py` | ✅ | Simple Colors (Trap/Wrap), Multi-Colors 1&2 |
| 12 | Uniqueness | `solver/uniqueness.py` | ✅ | Uniqueness Tests 1–6, Hidden Rectangle, BUG+1 (AR1/AR2 skipped — require givens tracking) |
| 13 | Basic fish | `solver/fish.py` | ✅ | X-Wing, Swordfish, Jellyfish (and larger) |
| 14 | Finned/Franken/Mutant fish | `solver/fish.py` | ⬜ | Finned, Sashimi, Franken, Mutant variants |
| 15 | Chains | `solver/chains.py` | ⬜ | X-Chain, XY-Chain, Remote Pair, Nice Loop/AIC |
| 16 | ALS | `solver/als.py` | ⬜ | ALS-XZ, ALS-XY-Wing, ALS-XY-Chain, Death Blossom, Sue de Coq |
| 17 | Forcing chains/nets | `solver/tabling.py` | ⬜ | Forcing Chain/Net (Contradiction + Verity), Grouped Nice Loop/AIC |
| 18 | Templates | `solver/templates.py` | ⬜ | Template Set, Template Delete |
| 19 | Brute force | `solver/brute_force.py` | ⬜ | Last-resort guess |

## Generator + public API

| # | Layer | File | Status | Notes |
|---|-------|------|--------|-------|
| 20 | Generator | `generator/generator.py` | ⬜ | Backtracking solver, uniqueness validation, puzzle generation |
| 21 | Public API | `api.py` | ⬜ | `Solver`, `Generator` classes matching the documented public surface |

---

## Validation approach

Every technique is validated by comparing our step sequence against HoDoKu's
`/vp` output on the same puzzle — same technique type, same cell, same digit,
in the same order.

- **Pure Python tests** — no HoDoKu needed, run instantly: `pytest -m "not hodoku"`
- **HoDoKu validation tests** — require `hodoku.jar` + Java: `pytest -m hodoku`
- Test corpus lives in `tests/puzzles/` (to be populated as techniques are added)

### Validation checkpoints reached

1. **Singles** (`tests/test_validate_singles.py`) — Full House, Naked Single,
   Hidden Single match HoDoKu step-for-step on easy puzzles.

2. **Intersections + Subsets** (`tests/test_validate_subsets.py`) — Locked
   Candidates 1&2, Locked/Naked/Hidden Pair/Triple/Quad match HoDoKu
   step-for-step including exact elimination sets.

3. **Single-digit patterns** (`tests/test_validate_single_digit.py`) — Skyscraper,
   2-String Kite, and Empty Rectangle elimination sets match HoDoKu on verified
   clean puzzles (only rows 1–9 techniques required). Test strategy: collect all
   eliminations of each type produced across the full solve and compare sorted lists.

4. **Wings** (`tests/test_validate_wings.py`) — W-Wing, XY-Wing, and XYZ-Wing all
   match HoDoKu on clean puzzles.

5. **Coloring** (`tests/test_validate_coloring.py`) — Simple Colors Trap and
   Multi-Colors 1 match HoDoKu. Simple Colors Wrap and Multi-Colors 2 require
   Finned X-Wing (row 14); parked as skipped tests.

6. **Uniqueness** (`tests/test_validate_uniqueness.py`) — UT1–4, UT6, and BUG+1
   all match HoDoKu on clean puzzles. UT5 and Hidden Rectangle pending test
   puzzles. Harness updated to parse BUG+1's colon-free `=>` output format.

7. **Basic fish** (`tests/test_validate_fish.py`) — X-Wing and Swordfish match
   HoDoKu on clean puzzles. Jellyfish pending test puzzle.

---

## Development scripts

| Script | Purpose |
|--------|---------|
| `scripts/find_clean_puzzle.py` | Generate random puzzles and find ones that are "clean" for a given technique (HoDoKu uses only already-implemented techniques). Use this to get test puzzles for new technique validation tests. |

```bash
# Find clean puzzles for XY-Wing (search seeds 0–1000)
python scripts/find_clean_puzzle.py --tech XY_WING --seeds 0-1000

# Add extra allowed techniques (e.g. when Wings depend on Colors)
python scripts/find_clean_puzzle.py --tech W_WING --allowed "XY-Wing" --seeds 0-500
```

### HoDoKu puzzle generation (batch mode)

HoDoKu has a `/s /sc` flag to generate puzzles matching specific criteria, but
it requires a full GUI/config environment and returns 0 results when run
headless from the command line.  **Use `find_clean_puzzle.py` instead.**

For reference, the intended syntax was:
```bash
# Generate puzzles where ER appears with only singles before/after (type :2)
MSYS_NO_PATHCONV=1 bash hodoku/hodoku.sh /s /sc "er:2" /o stdout
# Types: :3=singles only, :2=SSTS before+singles after, :1=SSTS before+after, :0=no restrictions
# Technique codes: er, sk, 2sk, bf3 (swordfish), xyw (XY-Wing), etc. (/lt to list all)
```

## Implementation notes

- Add each new technique to `SudokuStepFinder.get_step()` in `step_finder.py`
- Add a `pytestmark = pytest.mark.hodoku` line to every validation test module
- Techniques within a file can be added incrementally; re-run validation after each
