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
1112 total   1062 passed   44 failed   6 xfailed
```

**~96% passing** (1062/1106 excluding xfail).

---

## Remaining failures — by category

### ALS nodes in grouped chains (44 failures)

| Code | Technique | Variants |
|------|-----------|---------|
| 0709 | Grouped CNL | variant 2 |
| 0710 | Grouped DNL | variants 3, 4 |
| 0711 | Grouped AIC | variants 3, 4 |

These variants set `AllowAlsInTablingChains=true` in Java's regression tester.
Java's implementation is in `TablingSolver.fillTablesWithAls()`, which adds ALS nodes to
the forward-propagation implication tables before expanding and checking loops.

**Investigation (2026-03-09):** We attempted to implement ALS-in-chains by adding
direct weak links `c1(j) → c2(k)` to the existing DFS link graph (for each ALS, each
ordered pair of candidates (j, k), c1 ∈ buddies_per_cand[j], c2 ∈ buddies_per_cand[k]).
This correctly models the semantic: "if c1 is ON with digit j, the ALS is locked on j,
eliminating k from all cells that see all ALS k-cells."

However, the approach causes exponential DFS blowup because:
- ALS links are all weak, so they multiply fanout at every weak step
- The DFS explores all combinations before the chain length limit (20) cuts it off
- A single test case timed out at 60 seconds (vs ~5s without ALS links)

**Root cause:** Java's tabling approach is BFS/forward-propagation: each cell-candidate
pair is visited at most once per table-filling pass. Our DFS cannot bound the search the
same way. To implement this correctly, we need to extend `tabling.py`'s `fillTables()`
with `fillTablesWithAls()` and then route grouped-NL results through the tabling
infrastructure (as Java does in `doGetNiceLoops()`).

**Status:** Deferred. The helper functions `_build_gnl_links_with_als()` and
`_has_als_link()` were written and are present in `chains.py` but not called. The right
fix is implementing `TablingSolver.fillTablesWithAls()` in `tabling.py`.

### Franken/Mutant fish (0 failures — all passing ✅)

Implemented in `fish.py` via `_find_generalized_fish_all()`. All 0330–0364 variants pass.

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

## Known xfails (5 entries)

| Lines | Reason |
|-------|--------|
| 1445, 1453, 1454, 1455, 1459 | ALS-XY-Chain: needs bidirectional RC traversal or chain length >6, which Java's default settings can't find either. Confirmed fails in Java HoDoKu v2.2.0. |
| 724 | Finned Franken Jellyfish: requires cross-type siamese (basic+finned in one pass). Java's `/bsa` also fails to find the step. |

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

### ALS-in-chains investigation (unsuccessful)

See "ALS nodes in grouped chains" above. The DFS approach is not viable; the tabling
approach is required.

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
