# reglib-1.3.txt Regression Suite — Status Report

## Overview

HoDoKu ships a technique-isolation test library (`reglib-1.3.txt`) that lives in the
sibling repo at `../HoDoKu/reglib-1.3.txt`. We ported this into our test suite at
`tests/reglib/`. Each entry reconstructs a specific pencilmark board state (given cells
+ manually deleted candidates) and asserts that a named technique fires and produces
exactly the expected eliminations or placements.

This is complementary to `tests/regression/` (exemplar solve-path tests): reglib tests
one technique in isolation on a fixed board; exemplar tests validate full head-to-head
solve paths against HoDoKu's CLI.

**No Java/HoDoKu JAR required** — board states are fully self-contained.

## Results (as of 2026-03-08)

```
1112 total   800 passed   264 failed   48 skipped
```

**75% passing** (800/1064 excluding skipped).

### What the `find_all` work accomplished

The reglib harness calls `finder.find_all(sol_type)` and checks whether the expected
elimination set appears *anywhere* in the returned list. Before this session, most
solvers fell back to `get_step()` (at most 1 result), causing false failures whenever
the expected step wasn't the first one found.

Work done to wire up `find_all` across all solvers:

| Solver | Method added | Pattern used |
|--------|-------------|--------------|
| `simple.py` | already done | scan-based collectors |
| `fish.py` | `find_all` + `_find_basic_fish_all`, `_find_finned_fish_all` | `seen_elims` dedup |
| `single_digit.py` | `find_all` + `_find_*_all` variants | `seen_elims` dedup |
| `wings.py` | `find_all` + `_find_wing_all`, `_find_w_wing_all` | `seen_elims` dedup |
| `coloring.py` | `find_all` + `_find_simple_colors_all`, `_find_multi_colors_all` | `seen_elims` dedup |
| `uniqueness.py` | `find_all` + `_find_ur_all`, collector param threaded through emit | optional `collector` arg |
| `als.py` | `find_all` + `_find_als_xz_all`, `_find_als_xy_wing_all`, `_find_als_xy_chain_all` | `deletes_map` already collected all |
| `chains.py` | `find_all` + `_find_x_chain_impl_all`, `_find_xy_type_all`, `_find_nice_loop_all` | `deletes_map` + type filter |
| `step_finder.py` | routed all `_*_TYPES` sets to their solver's `find_all` | dispatch table |

This fixed approximately **96 false failures** (360 → 264).

## Remaining 264 failures — by category

### Bugs in existing implementations (~183 failures)

| Code | Technique | Count | Root cause |
|------|-----------|-------|-----------|
| 0708 | AIC | 34 | chains.py misses some AIC patterns |
| 0711 | Grouped AIC | 21 | chains.py grouped-node patterns incomplete |
| 0710 | Grouped DNL | 19 | chains.py grouped-node patterns incomplete |
| 0709 | Grouped CNL | 7 | chains.py grouped-node patterns incomplete |
| 0603 | Uniqueness Test 4 | 10 | uniqueness.py partial |
| 0606 | Hidden Rectangle | 10 | uniqueness.py partial |
| 0600 | Uniqueness Test 1 | 9 | uniqueness.py partial |
| 0601/02/04/05 | UT2/3/5/6 | 5 | uniqueness.py partial |
| 0321 | Sashimi Swordfish | 17 | fish.py sashimi detection bug |
| 0320 | Sashimi X-Wing | 9 | fish.py sashimi detection bug |
| 0322 | Sashimi Jellyfish | 9 | fish.py sashimi detection bug |
| 0311/12 | Finned Swordfish/Jellyfish | 7 | fish.py finned partial |
| 0402 | Empty Rectangle | 6 | single_digit.py ER bug |
| 0902/03 | ALS-XY-Wing/Chain | 10 | als.py partial patterns |
| 0904 | Death Blossom | 9 | als.py partial |

### Not implemented (~83 failures)

| Code | Technique | Count | Notes |
|------|-----------|-------|-------|
| 0607/08 | Avoidable Rectangle 1/2 | 25 | Requires tracking placed-but-not-given cells |
| 0342 | Finned Franken Jellyfish | 13 | Franken/Mutant fish family |
| 0341 | Finned Franken Swordfish | 8 | Franken/Mutant fish family |
| 0340 | Finned Franken X-Wing | 4 | Franken/Mutant fish family |
| 0332 | Franken Jellyfish | 4 | Franken/Mutant fish family |
| 0331 | Franken Swordfish | 3 | Franken/Mutant fish family |
| 0362/63/64 | Finned Mutant Jellyfish/larger | 8 | Mutant fish family |
| 0404 | Dual Two-String Kite | 9 | single_digit.py missing |
| 0405 | Dual Empty Rectangle | 8 | single_digit.py missing |

### Skipped (48 entries)

Techniques with no implementation at all — skipped by `_SKIP_CODES` in the test file:

| Code | Technique |
|------|-----------|
| 1101 | Sue de Coq |
| 1201 | Template Set |
| 1202 | Template Delete |
| 1301/02 | Forcing Chain Contradiction/Verity |
| 1303/04 | Forcing Net Contradiction/Verity |

## Running the suite

```bash
# Full run (~2 min)
pytest tests/reglib/ -q

# Single technique by code
pytest tests/reglib/ -k "0708" -v

# Quick smoke test (first 50 entries)
pytest tests/reglib/ -k "0000 or 0002 or 0003 or 0100" -v
```
