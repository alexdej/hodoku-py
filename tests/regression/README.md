# regression — Full Solve-Path Regression Suite

This directory contains a head-to-head regression suite that compares our
solver's complete solution path against HoDoKu's output, step for step.

## What it tests

Each puzzle in `exemplars-1.0.txt` is solved by both our solver and the HoDoKu
JAR. The test passes only if the two solution paths match exactly — same
techniques, same cells, same eliminations, in the same order. This validates
not just correctness but full fidelity to HoDoKu's behaviour, including
tie-breaking and ordering.

This is complementary to `tests/reglib/` (which tests individual techniques in
isolation on fixed pencilmark boards). The exemplar suite tests the full solve
loop end-to-end.

**Requires Java** — the HoDoKu JAR is invoked at test time to generate the
ground-truth solution paths.

## Test data

`exemplars-1.0.txt` is a UTF-16 LE text file containing puzzles grouped into
sections by technique. The format is documented on the
[HoDoKu exemplars page](https://hodoku.sourceforge.net/en/libs.php#libex).

Each section begins with a header:

```
#NNNN: Technique Name
```

Followed by puzzle lines:

```
<81-char puzzle string> # optional annotation
```

Puzzles inherit the technique code from the most recent section header. The
technique code is used for filtering and test IDs but is otherwise informational
— the ground truth comes from HoDoKu itself, not from the section label.

## Running

```bash
# Default run (first 10 puzzles per section, requires Java)
pytest tests/regression/ -v

# Run more puzzles
pytest tests/regression/ --exemplar-count 50 -v

# Restrict to one technique section
pytest tests/regression/ --exemplar-section 0901 -v

# Combine: first 20 ALS-XZ puzzles
pytest tests/regression/ --exemplar-section 0901 --exemplar-count 20 -v
```

## Known failures

`known_failures.txt` lists test IDs that are expected to fail (xfail). These
are puzzles where our solve path diverges from HoDoKu's due to known
unimplemented or buggy techniques. Tests listed here will be marked `xfail`
rather than `FAILED`, keeping the suite green while tracking outstanding work.

To regenerate the known failures list after fixing bugs:

```bash
python scripts/update_known_failures.py
```

## How it works

1. All puzzles in the run are batched and solved by the HoDoKu JAR (via
   `hodoku/hodoku.sh`) in a single session to amortize JVM startup cost.
2. Each puzzle is also solved by our `SudokuSolver`.
3. The two solution paths are compared step by step. On mismatch, the test
   reports the first diverging step.
