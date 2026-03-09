# sdm — Broad-Variety Puzzle Regression Suite

This directory contains a broad-coverage regression suite that runs our solver
against large puzzle collections in `.sdm` format and compares each solution
path against HoDoKu's output step for step.

## What it tests

Where `tests/regression/` uses a curated set of exemplar puzzles (one per
technique), this suite is designed for volume testing across a wide variety of
real-world puzzles. It's useful for catching regressions that don't show up in
the targeted exemplar suite, and for measuring overall solve-path fidelity
across difficulty ranges.

**Requires Java** — the HoDoKu JAR is invoked at test time.

## Test data format

`.sdm` files are plain text, one puzzle per line (81 characters, digits and
dots). Lines beginning with `#` are section labels that appear in test IDs and
failure output. Puzzle lines that are commented out (`# ` followed by 81
digits/dots) are silently skipped.

Puzzle files are not included in this repo. Place them in `tests/testdata/` or
provide an explicit path via `--sdm-file`.

## Running

```bash
# Run all puzzles in a file
pytest tests/sdm/ --sdm-file top1465 -v

# Sample a random subset (reproducible with --sdm-seed)
pytest tests/sdm/ --sdm-file top1465 --sdm-count 50 -v
pytest tests/sdm/ --sdm-file top1465 --sdm-count 50 --sdm-seed 7 -v

# Large file, small sample
pytest tests/sdm/ --sdm-file sudocue_top10000 --sdm-count 100 -v

# Absolute path
pytest tests/sdm/ --sdm-file /path/to/puzzles.sdm --sdm-count 200 -v
```

`--sdm-file` accepts:
- A bare stem like `top1465` (looked up in `tests/testdata/top1465.sdm`)
- A path relative to the project root
- An absolute path

## How it works

1. The SDM file is parsed and puzzles are sampled (all, or `--sdm-count`
   random puzzles seeded by `--sdm-seed`).
2. All puzzles are batched and solved by the HoDoKu JAR in a single session to
   amortize JVM startup cost.
3. Each puzzle is also solved by our `SudokuSolver`.
4. The two solution paths are compared step by step. On mismatch, the test
   reports the first diverging step.
