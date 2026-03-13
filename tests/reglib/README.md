# reglib — Technique-Isolation Regression Suite

This directory contains a port of HoDoKu's built-in regression test library.
Each of the 1112 test cases reconstructs a specific pencilmark board state and asserts that
exactly one named technique fires with exactly the expected eliminations or
placements.

## What it tests

Unlike [`tests/parity/`](../parity/README.md) which compares full solution paths
head-to-head against HoDoKu, reglib tests are executed against hodoku-py alone. 
Each entry is self-contained: the board state is fully specified by givens plus a list 
of manually deleted candidates.

This makes reglib tests (comparatively) fast and ideal for isolating individual
technique implementations.

## Test data

[`reglib-1.3.txt`](reglib-1.3.txt) is borrowed from the HoDoKu 2.2.0 source. The format is
documented on the [HoDoKu library page](https://hodoku.sourceforge.net/en/libs.php#libreg).

Each test case line looks like:

```
:<technique_code[-variant|x]>:<target_digits>:<givens_with_plus>:<deleted_cands>:<eliminations>:<placements>:<extra>:
```

- **technique_code**: 4-digit code identifying the technique (e.g. `0901` =
  `ALS-XZ`). A `-N` suffix is a numeric variant that affects solver options; a
  `-x` suffix marks a fail case (the technique must NOT fire).
- **target_digits**: digit(s) targeted by the technique.
- **givens_with_plus**: 81-char puzzle string; `+` before a digit marks a
  placed (non-given) cell.
- **deleted_cands**: candidates manually removed beyond standard Sudoku logic,
  space-separated as `<digit><row><col>` (1-indexed).
- **eliminations** / **placements**: expected output, same format.
- **extra**: metadata such as chain length (not validated by our tests).

Additionally tests are grouped according to header comments in the file:
```
#<technique_code>: <technique_name>
```

Each test case is then assigned a unique ID according to the pattern `{technique_code}_{technique_name}{variant}_{line_number}`, e.g.:

```
0901_ALS-XZ_842
0902_ALS-XY-Wing-2_1440
0904_Death_Blossom-x_1480
```

## How to run

```bash
# Full test suite (~2 min, all 1127 tests), quiet
pytest tests/reglib/ -q

# Limit to one technique (prefix match on technique_code)
pytest tests/reglib/ --reglib-section 0901 -v

# Limit to one technique (keyword match on name)
pytest tests/reglib/ -k "ALS-XY-Wing" -v

# Limit to first 5 entries (useful for quick smoke tests)
pytest tests/reglib/ --reglib-section 0708 --reglib-count 5 -v
```

Custom Flags:

- `--reglib-section CODE`: run only entries whose 4-digit technique code starts
  with `CODE`. Use this for stable prefix filters such as one exact technique
  (`0901`) or a family (`09` for ALS, `07` for chains).
- `--reglib-count N`: run only the first `N` tests from the matched group

`pytest` flags:

- `-k EXPR`: keyword match against the generated test id, for example
  `0902_ALS-XY-Wing-2_1440`. Use this for ad hoc selection by code, technique
  name, variant, line number, or arbitrary boolean combinations.
- `-q`: quieter output.
- `-v`: verbose output, including each generated reglib test id.



## Results (as of 2026-03-09)

```
1127 total   1106 passed   0 failed   6 xfailed   15 skipped
```

All implemented techniques pass. The 6 xfails are known limitations shared
with or analogous to Java HoDoKu v2.2.0 (see below).

## Known Issues

| Codes | Reason | HoDoKu | hodoku-py |  Status  |
|-------|--------|--------|-----------|----------|
| `0903_ALS-XY-Chain-1_1445`<br>`0903_ALS-XY-Chain-1_1453`<br>`0903_ALS-XY-Chain-1_1454`<br>`0903_ALS-XY-Chain-1_1455`<br>`0903_ALS-XY-Chain_1459` | `ALS-XY-Chain` (`0903`): needs bidirectional RC traversal or chain length >6, which Java's default `allStepsAlsChainForwardOnly=true` / `getAllStepsAlsChainLength=6` can't find. | 🔴 `No step found` | 🔴 `No step found` | 🟠 `xfail` |
| `0342_Finned_Franken_Jellyfish-1_724` | The Finned Franken Jellyfish test group (`0342`) requires cross-type siamese detection (basic+finned fish sharing a base, detected in a single pass with `fishType=UNDEFINED`). hodoku-py runs basic and finned fish searches separately, so the two fish never enter `_apply_siamese()` together. | 🟢 Correct | 🔴 `No step found` | 🟠 `xfail` |
| `0711_Grouped_AIC-4_1346` | In this one Grouped AIC test case HoDoKu finds variant 7 instead of expected variant 9. hodoku-py finds the right variant. | 🔴 Wrong variant | 🟢 Correct | 🟢 `pass` | 
`0707_Discontinuous_Nice_Loop-2_1181`<br>`0707_Discontinuous_Nice_Loop-2_1183`<br>`0707_Discontinuous_Nice_Loop-2_1185`<br>`0707_Discontinuous_Nice_Loop-2_1187`<br>`0707_Discontinuous_Nice_Loop-2_1190` | A number of Discontinuous Nice Loop tests were disabled in `reglib-1.3.txt`. HoDoKu finds a valid DNL but the wrong variant (different elimination cell). We find the expected variant. Related to the same chain enumeration order divergence as `0711_Grouped_AIC-4_1346`. | 🔴 Wrong variant | 🟢 Correct | ⬜ `skip` |
| `0110_Locked_Pair-1_326`<br>`0110_Locked_Pair-2_328`<br>`0110_Locked_Pair-2_329`<br>`0110_Locked_Pair-2_330`<br>`0110_Locked_Pair-2_331`<br>`0111_Locked_Triple-2_350`<br>`0111_Locked_Triple-2_351`<br>`0111_Locked_Triple-2_352`<br>`0111_Locked_Triple-2_353`<br>`0111_Locked_Triple-2_354` | Some of the tests in the Locked Pair and Locked Triple sections are disabled in `reglib-1.3.txt`. Per the comments in the file these look like regressions in HoDoKu `2.2`. These tests may have passed with a previous version of HoDoKu. | 🔴 Not implemented | 🔴 Mismatch | ⬜ `skip` |


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
`reglib-1.3.txt` (from `2.2.0`, our target) and `reglib-1.4.txt` (from the unreleased `2.3` branch).

## Relevant implementation details

### ALS nodes in grouped chains

Variants `0709-2`, `0710-3` and `0710-4`, and `0711-3` and `0711-4` all set `AllowAlsInTablingChains=true`.
These are handled by creating a `TablingSolver` directly in the test harness
(`_find_all_steps()` in `test_reglib.py`), which calls `fillTablesWithAls()`
to add ALS entries to the tabling implication tables before searching for
nice loops and AICs.

### `for_candidate` optimization for Fish

The Fish tests are the slowest part of the test suite. To speed things along,
our test harness "cheats" a little: it passes the `target_digits` field
 to `find_all()` as `for_candidate`. This restricts the Fish search to a single digit,
 resulting in a significant speedup in the tests (up to ~9x for the largest types of Fish).
 The validation logic is still consistent with HoDoKu's regression test: the test still checks 
 that the targeted elimination is found; it just doesn't find any _other_ eliminations that might 
 be present but not evaluated by the test, whereas HoDoKu would have found those as well but discarded them.
