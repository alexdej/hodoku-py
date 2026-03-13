# parity — Head-to-Head HoDoKu Comparison Suite

This directory contains the parity test suite that runs our solver against
puzzle files and compares each solution path step-for-step against HoDoKu's
output via [Py4J](https://www.py4j.org/).

## What it tests

Solve-path fidelity: same technique type, same eliminations, same placements,
in the same order. For techniques where HoDoKu provides context data (indices,
values), we verify those match too.

**Requires Java** — a JVM is started via Py4J to run HoDoKu at test time.

## Test data format

Puzzle files are plain text, one puzzle per line (81 characters, digits and
dots/zeros). Lines beginning with `#` are section labels that appear in test
IDs and failure output.

Puzzle files live in `tests/testdata/`.

## Running

```bash
# Run all puzzles in a file
pytest tests/parity/ --puzzle-file exemplars-1.0 -v

# Sample a random subset (reproducible with --puzzle-seed)
pytest tests/parity/ --puzzle-file top1465 --puzzle-count 50 -v
pytest tests/parity/ --puzzle-file top1465 --puzzle-count 50 --puzzle-seed 7 -v

# Filter by section or test name
pytest tests/parity/ --puzzle-file exemplars-1.0 -k "XY_Wing" -v

# Use the batch CLI backend instead of the default Py4J persistent JVM
pytest tests/parity/ --puzzle-file exemplars-1.0 --hodoku-backend batch -v
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--puzzle-file` | *(required)* | Puzzle file to run. Accepts a bare stem, project-relative path, or absolute path. |
| `--puzzle-count N` | all | Randomly sample N puzzles from the file. |
| `--puzzle-seed N` | 42 | RNG seed for `--puzzle-count` sampling. |
| `--hodoku-backend` | `py4j` | HoDoKu backend: `py4j` (persistent JVM via Py4J) or `batch` (CLI subprocess per chunk). |

`--puzzle-file` accepts:
- A bare stem like `exemplars-1.0` (looked up in `tests/testdata/exemplars-1.0.txt`)
- A path relative to the project root
- An absolute path

## How it works

1. The puzzle file is parsed and puzzles are optionally sampled
   (`--puzzle-count` with `--puzzle-seed`).
2. Each puzzle is solved by HoDoKu via a persistent Py4J gateway (one JVM
   for the entire session).
3. Each puzzle is also solved by our `SudokuSolver`.
4. The two solution paths are compared step by step using an asymmetric rule:
   - Type, eliminations, and placements must always match.
   - If HoDoKu provides indices/values context, ours must match.
   - If HoDoKu's context is empty (e.g. chains), the check is skipped.
5. On mismatch, the test reports the first diverging step with details.

A 30-second per-puzzle timeout (Unix only) prevents hangers from blocking the
run.
