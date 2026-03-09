# reglib-1.3.txt Regression Suite — Status Report

## Overview

HoDoKu ships a technique-isolation test library (`reglib-1.3.txt`). We ported it into
`tests/reglib/`. Each entry reconstructs a specific pencilmark board state (given cells +
manually deleted candidates) and asserts that a named technique fires with exactly the
expected eliminations or placements.

Complementary to `tests/regression/` (exemplar solve-path tests): reglib tests one
technique in isolation on a fixed board.

**No Java/HoDoKu JAR required** — board states are fully self-contained.

---

## Results (as of 2026-03-09)

```
1112 total   1106 passed   0 failed   6 xfailed
```

**~100% passing** (1106/1112 excluding xfail).

---

## Remaining failures — by category

### ALS nodes in grouped chains (0 failures — all passing ✅)

| Code | Technique | Variants |
|------|-----------|---------|
| 0709 | Grouped CNL | variant 2 |
| 0710 | Grouped DNL | variants 3, 4 |
| 0711 | Grouped AIC | variants 3, 4 |

These variants set `AllowAlsInTablingChains=true` in Java's regression tester.
Implemented via `TablingSolver.fillTablesWithAls()` in `tabling.py`, which adds ALS nodes
to the forward-propagation implication tables before expanding and checking loops.
The test harness (`test_reglib.py`) creates a `TablingSolver` directly for these variants.

**History:** An earlier DFS-based approach (adding ALS weak links to the chain graph)
caused exponential blowup. The correct fix was the BFS/tabling approach, matching Java's
`TablingSolver.fillTablesWithAls()`. A separate bug — house strong links being added to
`on_table` instead of `off_table` in `_fill_tables()` — was the root cause of all 44
failures. See "House strong link fix" in session history below.

### Franken/Mutant fish (0 failures — all passing ✅)

Implemented in `fish.py` via `_find_generalized_fish_all()`. All 0330–0364 variants pass.

**Performance:** Mutant Squirmbag (size 5) and Whale (size 6) have enormous search spaces
(C(21,5)² ≈ 414M and C(24,6) = 134K base combos respectively). Two optimizations make
these tractable:

1. **C accelerator** (`_fish_accel.c`): The cover-combination DFS loop is implemented in C
   via ctypes. 81-bit candidate masks are split into lo/hi uint64 halves (like Java's M1/M2).
   Speedup: ~30-100x vs pure Python (Squirmbag: 0.6s vs 17s, Whale: 5s vs timeout).
   Compiled: `gcc -O2 -shared -fPIC -o _fish_accel.so _fish_accel.c`
   Falls back to pure Python DFS with pruning if .so is unavailable.

2. **`for_candidate` parameter**: `find_all(sol_type, for_candidate=digit)` restricts the
   search to a single digit (like Java's `getAllFishes(forCandidate)`). The reglib test
   harness extracts the target digit from `candidates_field` and passes it through, reducing
   work ~9x for large fish.

**Note on test 724 (0342 Finned Franken Jellyfish, line 724):** This test was
investigated separately. Java's `/bsa` output does not find the expected step either.
Root cause: Java's `getAllFishes()` runs with `fishType=UNDEFINED`, collecting basic
AND finned fish in one pass before applying siamese. The expected elimination
`{r4c9<>4, r5c9<>4, r8c9<>4}` requires siamese between a basic Franken Jellyfish
`{r8c9<>4}` and a finned Franken Jellyfish `{r4c9<>4, r5c9<>4}` sharing the same base
(rows 1,2,6 + block 3). Our fish.py runs basic and finned searches separately, so those
two fish never enter the siamese matcher together.

Test 724 is marked `xfail` in `_CROSS_TYPE_SIAMESE_XFAIL`.

### Templates (18 failures)

| Code | Technique | Count |
|------|-----------|-------|
| 1201 | Template Set | ~9 |
| 1202 | Template Delete | ~9 |

`solver/templates.py` not yet implemented. Template Set/Delete precompute all 46,656
candidate templates for each digit and use AND/OR intersection to find forced placements
and eliminations.

---

## Known xfails (6 entries)

| Lines | Reason | Java status |
|-------|--------|-------------|
| 1445, 1453, 1454, 1455, 1459 | ALS-XY-Chain (0903): needs bidirectional RC traversal or chain length >6, which Java's default `allStepsAlsChainForwardOnly=true` / `getAllStepsAlsChainLength=6` can't find. | Also fails ("No step found!") |
| 724 | Finned Franken Jellyfish (0342): requires cross-type siamese (basic+finned fish sharing a base, detected in a single pass with `fishType=UNDEFINED`). Our code runs basic and finned fish searches separately, so the two fish never enter `_apply_siamese()` together. | Passes (unified fish search) |

**Note:** Java has one additional failure we don't: `0711:59` (Grouped AIC) — Java finds
variant 7 instead of expected variant 9. Our code finds the correct variant.

---

## Session history (2026-03-09)

### Group node lasso fix

Fixed a bug in `_dfs_nl` (chains.py) where the start_cell bit in `chain_occupied` was
incorrectly preventing group nodes that contain the start cell from being visited.

**Example chain** (test 1280): `r9c4 -8- r7c5 -7- r9c456 =7= r9c8 =6= r9c4`

Here start_cell = r9c4 (index 75). Group node r9c456 has cells {75, 76, 77}. When the
DFS reaches r9c456, `end_mask & chain_occupied` fired because bit 75 was set (start_cell
was added at initialization). Since `is_end_group=True`, the old code skipped it as a
lasso — but r9c456 containing start_cell doesn't create a cycle; the chain later closes
by returning to r9c4 via a strong link, which is a valid loop.

**Fix:** Only block group nodes if their cells overlap with *interior* chain cells
(chain_occupied excluding start_cell):

```python
if end_mask & chain_occupied:
    if is_end_group:
        if end_mask & (chain_occupied & ~(1 << start_cell)):
            continue  # true lasso: overlaps interior cell
    elif end_cell != start_cell:
        continue  # lasso
    else:
        is_loop = True
```

Tests fixed: line 1280 (Grouped DNL-2), line 1321 (Grouped AIC-2).

### House strong link fix (fixed all 44 ALS-in-tabling failures)

In `_fill_tables()` (tabling.py), the house strong link — when exactly 2 cells have a
candidate in a house, deleting from one forces the other ON — was incorrectly added to
`on_entry` (on_table) instead of `off_entry` (off_table).

Java reference: `TablingSolver.java` line 1862:
`offTable[i * 10 + cand].addEntry(tmpSet.get(0), cand, true)`

Our code had: `on_entry.add_entry_simple(peer, cand, True)` — WRONG.
Fixed to: `off_entry.add_entry_simple(peer, cand, True)` — CORRECT.

The on_table version created contradictory entries ("setting cand in cell i also sets cand
in peer" — impossible since they share a house), corrupting table expansion and causing
wrong chain reconstruction.

### ALS-in-chains investigation (historical — superseded by house strong link fix)

Before the house strong link fix was found, we attempted a DFS approach: adding ALS weak
links directly to the chain graph. This caused exponential blowup and was abandoned. The
actual root cause was the table corruption from the wrong-table bug above — once fixed,
the existing tabling infrastructure (including `fillTablesWithAls()`) worked correctly.

### Mutant fish performance fix (C accelerator)

Mutant Squirmbag (size 5, 0363) and Whale (size 6, 0364) caused the test suite to
hang (>500s) due to the combinatorial explosion in the cover search loop. For digit 9
on the Squirmbag test puzzle, C(21,5)² ≈ 414M inner loop iterations.

**Root cause:** CPython is ~50-100x slower than Java's JIT for tight numeric loops with
81-bit bitwise operations. Optimizations tried:

1. `bin(x).count('1')` → `.bit_count()`: 7-10x speedup in popcount (200ns→20ns per call)
2. DFS with zero-fins pruning: ~30% fewer nodes but Python DFS overhead offsets gains
3. Suffix-OR pruning: marginal improvement (most cover sets collectively cover all base cells)
4. `for_candidate` parameter: ~9x reduction (search 1 digit instead of all 9)

None of these were sufficient. Final solution: **C extension** (`_fish_accel.c`) for the
cover DFS loop, loaded via ctypes. This brings Squirmbag from 17s→0.6s and Whale from
timeout→5s, matching Java's performance order-of-magnitude.

---

## Running the suite

```bash
# Full run (~10 min)
pytest tests/reglib/ -q

# Single technique
pytest tests/reglib/ -k "0711" -v

# Only grouped chain variants
pytest tests/reglib/ -k "0709 or 0710 or 0711" -v
```
