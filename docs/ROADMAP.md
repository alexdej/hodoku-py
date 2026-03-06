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
| 9 | Single-digit patterns | `solver/single_digit.py` | ⬜ | Skyscraper, 2-String Kite, Empty Rectangle, Turbot Fish |
| 10 | Wings | `solver/wings.py` | ⬜ | XY-Wing, XYZ-Wing, W-Wing |
| 11 | Coloring | `solver/coloring.py` | ⬜ | Simple Colors (Trap/Wrap), Multi-Colors |
| 12 | Uniqueness | `solver/uniqueness.py` | ⬜ | Uniqueness Tests 1–6, BUG+1, Hidden/Avoidable Rectangle |
| 13 | Basic fish | `solver/fish.py` | ⬜ | X-Wing, Swordfish, Jellyfish (and larger) |
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

---

## Implementation notes

- Add each new technique to `SudokuStepFinder.get_step()` in `step_finder.py`
- Add a `pytestmark = pytest.mark.hodoku` line to every validation test module
- Techniques within a file can be added incrementally; re-run validation after each
