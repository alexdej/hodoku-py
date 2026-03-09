# reglib — Technique-Isolation Regression Suite

This directory contains a port of HoDoKu's built-in regression test library.
Each test case reconstructs a specific pencilmark board state and asserts that
exactly one named technique fires with exactly the expected eliminations or
placements.

## What it tests

Unlike `tests/regression/` (which validates full head-to-head solve paths
against the HoDoKu JAR), reglib tests are **pure Python** — no JVM or HoDoKu
binary required. Each entry is self-contained: the board state is fully
specified by givens plus a list of manually deleted candidates.

This makes reglib tests fast, hermetic, and ideal for isolating individual
technique implementations.

## Test data

`reglib-1.3.txt` is copied from the HoDoKu 2.2.0 source. The format is
documented on the [HoDoKu library page](https://hodoku.sourceforge.net/en/libs.php#libreg).

Each data line looks like:

```
:<technique_code[-variant|x]>:<candidates>:<givens_with_plus>:<deleted_cands>:<eliminations>:<placements>:<extra>:
```

- **technique_code**: 4-digit code identifying the technique (e.g. `0901` =
  ALS-XZ). A `-N` suffix is a numeric variant that affects solver options; a
  `-x` suffix marks a fail case (the technique must NOT fire).
- **candidates**: digit(s) targeted by the technique.
- **givens_with_plus**: 81-char puzzle string; `+` before a digit marks a
  placed (non-given) cell.
- **deleted_cands**: candidates manually removed beyond standard Sudoku logic,
  space-separated as `<digit><row><col>` (1-indexed).
- **eliminations** / **placements**: expected output, same format.
- **extra**: metadata such as chain length (not validated by our tests).

## Running

```bash
# Full suite (~2 min, ~1100 tests)
pytest tests/reglib/ -q

# Single technique by code
pytest tests/reglib/ -k "0901" -v

# Technique family prefix
pytest tests/reglib/ --reglib-section 09 -v

# Limit to first N entries (useful for quick smoke tests)
pytest tests/reglib/ --reglib-section 0708 --reglib-count 5 -v
```

## Results (as of 2026-03-09)

```
1112 total   1106 passed   0 failed   6 xfailed
```

All implemented techniques pass. The 6 xfails are known limitations shared
with or analogous to Java HoDoKu v2.2.0 (see below).

## Variant flags

HoDoKu's regression tester (`RegressionTester.java`) sets specific solver
options per technique and variant before running each test. Our harness
(`test_reglib.py`) mirrors these:

| Technique | Variant | Option |
|-----------|---------|--------|
| SKYSCRAPER, TWO_STRING_KITE | any | `AllowDualsAndSiamese=false` |
| DUAL_TWO_STRING_KITE | any | `AllowDualsAndSiamese=true` |
| EMPTY_RECTANGLE | 1 | `AllowErsWithOnlyTwoCandidates=true` |
| DUAL_EMPTY_RECTANGLE | any | `AllowErsWithOnlyTwoCandidates=true`, `AllowDualsAndSiamese=true` |
| UNIQUENESS_* / HIDDEN_RECT / AR1/2 | 1 | `AllowUniquenessMissingCandidates=false` |
| UNIQUENESS_* / HIDDEN_RECT / AR1/2 | 2 | `AllowUniquenessMissingCandidates=true` |
| SWORDFISH/JELLYFISH (and finned/sashimi) | any | `AllowDualsAndSiamese=true` |
| ALS_XY_WING | 2 | `AllowAlsOverlap=true` |
| ALS_XY_CHAIN | 2 | `AllowAlsOverlap=true` |
| DEATH_BLOSSOM | 2 | `AllowAlsOverlap=true` |
| GROUPED_CNL | 2 | `AllowAlsInTablingChains=true` |
| GROUPED_DNL | 3, 4 | `AllowAlsInTablingChains=true` |
| GROUPED_AIC | 3, 4 | `AllowAlsInTablingChains=true` |
| AIC, DNL, CNL | any | `OnlyOneChainPerStep=false` |
| X_CHAIN, XY_CHAIN, REMOTE_PAIR | any | `OnlyOneChainPerStep=false` |

See `docs/HODOKU_VERSIONS.md` for the full story, including differences between
reglib-1.3 (2.2.0, our target) and reglib-1.4 (unfinished 2.3 branch).

## Test IDs

Test IDs follow the pattern `{code}_{name}{variant}_{line_number}`, e.g.:

```
0901_ALS-XZ_842
0902_ALS-XY-Wing-2_1440
0904_Death_Blossom-x_1480
```

## Known xfails (6 entries)

| Lines | Reason | Java status |
|-------|--------|-------------|
| 1445, 1453, 1454, 1455, 1459 | ALS-XY-Chain (0903): needs bidirectional RC traversal or chain length >6, which Java's default `allStepsAlsChainForwardOnly=true` / `getAllStepsAlsChainLength=6` can't find. | Also fails ("No step found!") |
| 724 | Finned Franken Jellyfish (0342): requires cross-type siamese detection (basic+finned fish sharing a base, detected in a single pass with `fishType=UNDEFINED`). Our code runs basic and finned fish searches separately, so the two fish never enter `_apply_siamese()` together. | Passes (unified fish search) |

Java has one additional failure we don't: `0711:59` (Grouped AIC) — Java finds
variant 7 instead of expected variant 9. Our code finds the correct variant.

### ALS-XY-Chain xfails (lines 1445, 1453, 1454, 1455, 1459)

These tests require either bidirectional RC (restricted common) traversal or
chains longer than 6 RCs. Java's defaults are `allStepsAlsChainForwardOnly=true`
and `getAllStepsAlsChainLength=6`, so Java also returns "No step found!" on all
five. Our implementation uses forward-only traversal with `_MAX_RC=50`, matching
Java's forward-only constraint. Marked as `_JAVA_XFAIL_LINES` in `test_reglib.py`.

### Cross-type siamese (line 724)

Java's `FishSolver.getAllFishes()` runs with `fishType=UNDEFINED`, which finds
both basic and finned Franken fish in a single pass. After collecting results,
`findSiameseFish()` detects pairs where a basic Franken Jellyfish and a finned
Franken Jellyfish share the same base — "cross-type siamese." The expected
elimination requires merging eliminations from both fish.

Our `fish.py` routes `FINNED_FRANKEN_JELLYFISH` and `FRANKEN_JELLYFISH` to
separate `find_all()` calls, so the two fish never enter `_apply_siamese()`
together. Fixing this would require a unified fish search (merging basic and
finned into one pass) — high effort and regression risk for a single test.
Marked as `_CROSS_TYPE_SIAMESE_XFAIL` in `test_reglib.py`.

## Notable implementation details

### C accelerator for Mutant fish

Mutant Squirmbag (size 5) and Whale (size 6) have enormous search spaces.
CPython is ~50-100x slower than Java JIT for tight bitwise loops. The cover
DFS is implemented in C (`solver/_fish_accel.c`) loaded via ctypes, with a
pure Python fallback. See `docs/ROADMAP.md` for details.

### ALS nodes in grouped chains

Variants 0709-2, 0710-3/4, 0711-3/4 set `AllowAlsInTablingChains=true`.
These are handled by creating a `TablingSolver` directly in the test harness
(`_find_all_steps()` in `test_reglib.py`), which calls `fillTablesWithAls()`
to add ALS entries to the tabling implication tables before searching for
nice loops and AICs.

### `for_candidate` optimization

The test harness extracts the target digit from each entry's `candidates_field`
and passes it as `for_candidate` to `find_all()`. This restricts fish search
to a single digit (~9x speedup for large fish).
