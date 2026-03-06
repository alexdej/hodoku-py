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
| 14 | Finned/Sashimi fish | `solver/fish.py` | ✅ | Finned X-Wing/Swordfish/Jellyfish, Sashimi variants (Franken/Mutant not implemented) |
| 15 | Chains | `solver/chains.py` | 🔧 | X-Chain ✅, XY-Chain ✅, Remote Pair ✅, DNL/CNL/AIC pending (see `memory/aic_nice_loop_notes.md`) |
| 16 | ALS | `solver/als.py` | ⬜ | ALS-XZ, ALS-XY-Wing, ALS-XY-Chain, Death Blossom, Sue de Coq |
| 17 | Forcing chains/nets | `solver/tabling.py` | ⬜ | Forcing Chain/Net (Contradiction + Verity), Grouped Nice Loop/AIC |
| 18 | Templates | `solver/templates.py` | ⬜ | Template Set, Template Delete — no puzzle-level validation test needed; `/s /sc ts` only works in GUI mode and examples are essentially unfindable headlessly. Test at unit level: verify AND/OR of 46,656 precomputed templates produces correct set/delete masks. |
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

5. **Coloring** (`tests/test_validate_coloring.py`) — Simple Colors Trap,
   Multi-Colors 1 & 2 all pass. Simple Colors Wrap still skipped (no clean
   puzzle found yet — needs a puzzle where Wrap fires with only SSTS before it).

6. **Uniqueness** (`tests/test_validate_uniqueness.py`) — UT1–6, Hidden Rectangle,
   and BUG+1 all pass. Harness updated to parse BUG+1's colon-free `=>` format.
   AR1/AR2 skipped permanently (require givens tracking not in our Grid).

7. **Basic fish** (`tests/test_validate_fish.py`) — X-Wing, Swordfish, and
   Jellyfish all pass.

8. **Finned/Sashimi fish** (`tests/test_validate_finned_fish.py`) — Finned
   X-Wing, Finned Swordfish, and Finned Jellyfish all pass. Sashimi variants
   implemented but no test puzzle yet. Franken/Mutant not implemented.

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

### HoDoKu puzzle search — `/s /sc` (works via direct java, not hodoku.sh)

```bash
cd hodoku
java -Xmx512m -jar hodoku.jar /s /sc hr
```

Replace `hr` with any technique code. Common codes: `hr` (hidden rectangle),
`bf2` (X-Wing), `bf3` (swordfish), `bf4` (jellyfish), `ut1`–`ut6`,
`sk` (skyscraper), `2sk` (2-string kite), `er` (empty rectangle),
`xyw` (XY-Wing), `sc` (simple colors), `mc` (multi colors). Run `/lt` for full list.

Output: `<puzzle> # <before-cat> <tech>(<count>) <after-cat>`
- Categories describe what comes **before** and **after** the target step
- `s` = Singles only, `ssts` = SSTS or below, `x` = beyond SSTS
- e.g. `# ssts hr(1) x` → SSTS steps before, 1 HR, then advanced steps after
- e.g. `# s hr(1) ssts` → only Singles before, 1 HR, then SSTS steps after
- Multiple hits: `# ssts hr(1) hr(1) x` → two separate HR steps in the solve

**Cleanness suffix** — append to technique code (e.g. `hr:2`):
- `:3` — Singles only before AND after ← **ideal**
- `:2` — SSTS before, Singles after ← **good fallback** (no "singles before, SSTS after" option)
- `:1` — SSTS before AND after (acceptable; we now implement all of SSTS)
- `:0` — unrestricted

**SSTS** = Singles + Locked Candidates + Subsets + X-Wing + Swordfish +
Jellyfish + XY-Wing + Simple Colors + Multi Colors. All implemented as of row 13.

## Parking lot

Techniques that are implemented in HoDoKu but not currently on the roadmap.
Revisit if needed, but don't block progress on them.

| Technique | Notes |
|-----------|-------|
| Franken fish | Fish using blocks as base/cover units (mixed row/col/block). Rare in practice, significant added complexity. |
| Mutant fish | Fully generalized fish — any combination of rows, cols, and blocks as base or cover. Even rarer. |
| Avoidable Rectangles (AR1/AR2) | Like Unique Rectangles but require tracking which cells were given vs. solved. Our Grid doesn't record givens. |

---

## Implementation notes

- Add each new technique to `SudokuStepFinder.get_step()` in `step_finder.py`
- Add a `pytestmark = pytest.mark.hodoku` line to every validation test module
- Techniques within a file can be added incrementally; re-run validation after each
