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
| 12 | Uniqueness | `solver/uniqueness.py` | ✅ | Uniqueness Tests 1–6, Hidden Rectangle, BUG+1, Avoidable Rectangle 1–2 |
| 13 | Basic fish | `solver/fish.py` | ✅ | X-Wing, Swordfish, Jellyfish (and larger) |
| 14 | Finned/Sashimi/Franken/Mutant fish | `solver/fish.py` | ✅ | Finned, Sashimi, Franken, Mutant — all sizes through Whale. Mutant Squirmbag/Whale use C accelerator (`_fish_accel.c`) for cover search performance. |
| 15 | Chains | `solver/chains.py` | ✅ | X-Chain, XY-Chain, Remote Pair, Turbot Fish, DNL, CNL, AIC, GDNL, GCNL, GAIC |
| 16 | ALS | `solver/als.py` | ✅ | ALS-XZ, ALS-XY-Wing, ALS-XY-Chain validated (`tests/test_validate_als.py`). Death Blossom implemented but unvalidatable: HoDoKu always finds a Forcing Chain first on any puzzle hard enough to need DB. |
| 17 | Forcing chains/nets | `solver/tabling.py` | ✅ | Forcing Chain/Net (Contradiction + Verity), Grouped Nice Loop/AIC with ALS nodes |
| 18 | Templates | `solver/templates.py` | ✅ | Template Set, Template Delete — AND/OR of 46,656 precomputed templates with iterative refinement. All 18 reglib tests passing. |
| 19 | Brute force | `solver/brute_force.py` | ✅ | Last-resort guess — `tests/test_brute_force.py` (pure unit tests, no HoDoKu needed) |

## Generator + public API

| # | Layer | File | Status | Notes |
|---|-------|------|--------|-------|
| 20 | Generator | `generator/generator.py` | ⬜ | Backtracking solver, uniqueness validation, puzzle generation |
| 21 | Public API | `api.py` | ⬜ | `Solver`, `Generator` classes matching the documented public surface |
| 22 | Bad input tests | `tests/test_bad_inputs.py` | ⬜ | See note below |

### Bad input / edge-case tests (row 22)

Before publishing, add a test module covering inputs the public API must
handle gracefully. Cases to cover:

| Input | Expected behaviour |
|-------|--------------------|
| Already-solved puzzle (81 filled, valid) | `solve()` returns `solved=True`, zero steps |
| Puzzle with no solution (contradiction in givens) | `solved=False` or raises a documented exception |
| Puzzle with multiple solutions (non-unique) | Solver solves one branch; `rate()` / `generate()` should reject or flag non-unique puzzles |
| Duplicate digit in a house (e.g. two 5s in same row) | Raise `ValueError` or return `solved=False` immediately |
| Wrong-length string (< 81 or > 81 chars) | Raise `ValueError` |
| Invalid characters (not 0–9 or `.`) | Raise `ValueError` |
| All-empty grid (`000…0`) | Solver runs brute force; returns a valid solution |
| Single given (hardest valid starting point) | Solver runs; terminates correctly |

These tests do not require HoDoKu. They belong in `tests/test_bad_inputs.py`
and should run in the default (non-`java`) pytest target. Implement
alongside or just after the public API (row 21).

---

## Validation approach

Every technique is validated by comparing our step sequence against HoDoKu's
`/vp` output on the same puzzle — same technique type, same cell, same digit,
in the same order. Goal is 100% fidelity.

- **Pure Python tests** — no HoDoKu needed, run instantly: `pytest -m "not java"`
- **HoDoKu validation tests** — require `hodoku.jar` + Java: `pytest -m java`
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
   implemented but no test puzzle yet. Franken/Mutant all passing in reglib.

9. **Chains** (`tests/test_validate_aic.py`) — X-Chain, XY-Chain, Remote Pair,
   DNL, CNL, and AIC all pass. Turbot Fish implemented.

11. **ALS** (`tests/test_validate_als.py`) — ALS-XZ, ALS-XY-Wing, and ALS-XY-Chain
    all pass on three clean puzzles. Death Blossom is implemented but no validation
    puzzle found: HoDoKu always reaches a Forcing Chain before DB can fire.

10. **Grouped Nice Loop** — GDNL, GCNL, and GAIC implemented and validated.
    Implementation: `_GroupNode`, `_collect_group_nodes()`, `_build_gnl_links()`
    in `chains.py`; `_dfs_nl` refactored to use integer node IDs and bitmask
    occupancy tracking. See `docs/SPEC_ROW17_GNL.md`.
    Note: variants requiring ALS nodes in chains (AllowAlsInTablingChains=true)
    now pass — implemented via `TablingSolver.fillTablesWithAls()` in `tabling.py`.

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
- `:2` — SSTS before, Singles after
- `:1` — SSTS before AND after ← **good fallback** (we now implement all of SSTS)
- `:0` — unrestricted (may be necessary for difficult techniques)

**SSTS** = Singles + Locked Candidates + Subsets + X-Wing + Swordfish +
Jellyfish + XY-Wing + Simple Colors + Multi Colors. All implemented as of row 13.

## Cross-cutting gaps

These are capabilities that HoDoKu exposes across all technique layers but that
we have not yet implemented. They are not tied to a single solver; each one
requires changes across most or all of the specialized solvers.

### `findAll*()` — enumerate all instances (highest priority)

HoDoKu exposes two parallel execution paths for every technique:

| Path | Our status | Used by |
|------|-----------|---------|
| `getStep(type)` → first match | **Implemented** | Solve loop (`/vp`) |
| `findAll*(type)` → all matches | **Implemented** | `/bsa` mode, reglib test harness |

All specialized solvers expose `find_all(sol_type)` and `SudokuStepFinder`
dispatches to them. The reglib harness uses this for technique-isolation tests.

### Remaining unimplemented techniques

| Technique | Code | Notes |
|-----------|------|-------|
| ALS nodes in grouped chains | 0709-2/0710-3,4/0711-3,4 | **Done.** Implemented via `tabling.py` `fillTablesWithAls()`. All reglib tests passing. |
| Sue de Coq | 1101 | **Done.** Implemented in `solver/misc.py`. All reglib tests passing. |
| Template Set/Delete | 1201/1202 | **Done.** Implemented in `solver/templates.py`. All 18 reglib tests passing. |
| Forcing Chain/Net | 1301-1304 | **Done.** Implemented in `solver/tabling.py`. All reglib tests passing. |

---

---

## Implementation notes

- Add each new technique to `SudokuStepFinder.get_step()` in `step_finder.py`
- Add a `pytestmark = pytest.mark.java` line to every validation test module
- Techniques within a file can be added incrementally; re-run validation after each

### C accelerator (`_fish_accel.c`)

The Mutant fish cover-combination search has a huge search space (up to C(24,6) = 134K
base combos × cover DFS for Whale). CPython is ~50-100x slower than Java JIT for tight
bitwise loops, making this intractable in pure Python.

`solver/_fish_accel.c` implements the cover DFS in C, loaded via `ctypes` at import time.
81-bit candidate masks are split into lo/hi `uint64` halves (matching Java's M1/M2).

- **Auto-compiles** on first import if `.so` is missing but `.c` exists (requires `gcc`/`cc`)
- **Falls back** to pure Python DFS with pruning if no C compiler is available
- **Performance**: Squirmbag 0.6s, Whale 5s (vs 17s/timeout in Python)
- **Packaging**: The `.so` is gitignored; `.c` source is committed. For distribution,
  the `.so` should be built as part of the package build step (future work).

If more hot loops need C acceleration in the future, follow the same pattern:
self-contained `.c` file, `ctypes` loading with auto-compile, Python fallback.

### HoDoKu compatibility: elimination ordering

When building a `SolutionStep`, **always add eliminations in ascending cell-index
order** (i.e. iterate `sorted(cells)`). Java's `SudokuSet` stores and iterates
elements in ascending order, so `addCandidateToDelete` is called lowest-index
first. The elimination order matters because `del_candidate` feeds the hidden-
single queue (`hs_queue`): the first eliminated cell's constraint changes hit the
queue first, and that determines which hidden single fires next. If our code
iterates an unordered Python `set` or a list built in traversal order, the queue
gets a different entry first and the solve path diverges from HoDoKu's.

**Checklist for new techniques:**
- Collect candidate cells into a sorted container, or call `sorted()` before
  the `add_candidate_to_delete` loop.
- Same applies to the hidden-single queue itself: Java's `SudokuSinglesQueue` is
  a plain FIFO populated in the order `del_candidate` is called, so elimination
  order is the only lever we have.
