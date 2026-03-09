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

## Variant flags

HoDoKu's regression tester sets specific solver options per technique and
variant before running each test. Our harness mirrors these:

| Technique | Variant | Option |
|-----------|---------|--------|
| ALS-XY-Wing | 2 | `allow_overlap=True` |
| ALS-XY-Chain | 2 | `allow_overlap=True` |
| Death Blossom | 2 | `allow_overlap=True` |

See `docs/HODOKU_VERSIONS.md` for the full story, including differences between
reglib-1.3 (2.2.0, our target) and reglib-1.4 (unfinished 2.3 branch).

## Test IDs

Test IDs follow the pattern `{code}_{name}{variant}_{line_number}`, e.g.:

```
0901_ALS-XZ_842
0902_ALS-XY-Wing-2_1440
0904_Death_Blossom-x_1480
```

## Current status

See `docs/REGLIB_STATUS.md` for a breakdown of passing/failing tests by
technique.
