# hodoku-py

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue)

A Python port of [HoDoKu](https://hodoku.sourceforge.net/)'s Sudoku solver, hint engine, and difficulty rater — no GUI, no dependencies.

The goal is bit-for-bit fidelity with HoDoKu 2.2.0: same techniques, same tie-breaking, same elimination order, same difficulty scores. This makes the library useful as a headless solver backend and as a reference implementation for Sudoku logic.

## Status

Core solver complete through ALS techniques. Generator and public API not yet implemented.

| Layer | Techniques | Status |
|-------|-----------|--------|
| Singles | Full House, Naked Single, Hidden Single | ✅ |
| Intersections + Subsets | Locked Candidates 1&2, Naked/Hidden Pair/Triple/Quad | ✅ |
| Single-digit patterns | Skyscraper, 2-String Kite, Empty Rectangle | ✅ |
| Wings | XY-Wing, XYZ-Wing, W-Wing | ✅ |
| Coloring | Simple Colors, Multi-Colors 1&2 | ✅ |
| Uniqueness | UT1–6, Hidden Rectangle, BUG+1 | ✅ |
| Fish | X-Wing through Whale; Finned/Sashimi, Franken, Mutant variants | ✅ |
| Chains | X-Chain, XY-Chain, Remote Pair, DNL, CNL, AIC, Grouped Nice Loops/AIC | ✅ |
| ALS | ALS-XZ, ALS-XY-Wing, ALS-XY-Chain, Death Blossom | ✅ |
| Forcing chains/nets | Contradiction + Verity | ⬜ |
| Templates | Template Set/Delete | ⬜ |
| Generator + public API | Puzzle generation, `Solver`/`Generator` classes | ⬜ |

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for full details and known gaps.

## Requirements

- Python 3.11+
- C compiler (optional) — auto-detected at runtime for Mutant fish acceleration. Without it, Mutant Whale (size 6) tests are skipped; everything else works in pure Python.

## Test requirements

The `reglib` suite is pure Python and has no extra requirements. The `regression` and `sdm` suites compare against the bundled HoDoKu JAR and require:

- Java (OpenJDK 17+)

## Installation

```bash
pip install -e ".[dev]"
```

## Running tests

There are three test suites:

### [reglib](tests/reglib/) — technique-isolation suite (pure Python, ~2 min, ~1100 tests)

Ports HoDoKu's built-in regression library. Each test reconstructs a fixed pencilmark board and asserts that one specific technique fires with the expected eliminations. No Java required.

```bash
pytest tests/reglib/ -q

# Single technique by code
pytest tests/reglib/ -k "0901" -v

# Technique family
pytest tests/reglib/ --reglib-section 09 -v
```

### [regression](tests/regression/) — exemplar suite (requires Java)

Full head-to-head solve-path comparison against the HoDoKu JAR on curated exemplar puzzles.

```bash
pytest tests/regression/ -v

# More puzzles per section
pytest tests/regression/ --exemplar-count 50 -v

# One technique section
pytest tests/regression/ --exemplar-section 0901 -v
```

### [sdm](tests/sdm/) — broad-variety suite (requires Java)

Volume testing against `.sdm` puzzle files (one puzzle per line). Puzzle files are not included; place them in `tests/testdata/`.

```bash
pytest tests/sdm/ --sdm-file top1465 -v
pytest tests/sdm/ --sdm-file top1465 --sdm-count 50 --sdm-seed 7 -v
```

### Skipping Java-dependent tests

```bash
pytest tests/ -m "not java"   # pure-Python tests only
```

## Docker

A development image with Python and Java pre-installed:

```bash
docker build -f docker/Dockerfile.dev -t hodoku-dev .
docker run -it --rm -v "$(pwd)":/workspace hodoku-dev

# Inside the container:
pytest tests/reglib/ -q
pytest tests/regression/ --exemplar-count 50 -q
```

## Development scripts

```bash
# Find a "clean" puzzle for validating a new technique
python scripts/find_clean_puzzle.py --tech XY_WING --seeds 0-1000

# Regenerate known_failures.txt after fixing bugs
python scripts/update_known_failures.py
```

## Project structure

```
src/hodoku/
├── core/          # Grid, CellSet, SolutionStep, enums, scoring
├── solver/        # One file per technique family + central dispatcher
│   ├── step_finder.py   # SudokuStepFinder — routes get_step() calls
│   ├── solver.py        # SudokuSolver — solve loop and difficulty rating
│   ├── simple.py        # Singles, locked candidates, subsets
│   ├── fish.py          # Basic, finned/sashimi, Franken, Mutant fish
│   ├── _fish_accel.c    # C accelerator for Mutant fish (auto-compiled)
│   ├── single_digit.py  # Skyscraper, 2-String Kite, Empty Rectangle
│   ├── uniqueness.py    # Uniqueness Tests 1–6, BUG+1
│   ├── wings.py         # XY-Wing, XYZ-Wing, W-Wing
│   ├── coloring.py      # Simple Colors, Multi-Colors
│   ├── chains.py        # X-Chain, XY-Chain, Nice Loop / AIC families
│   └── als.py           # ALS-XZ, ALS-XY-Wing, ALS-XY-Chain, Death Blossom
└── generator/     # Backtracking solver (puzzle generation not yet wired)

hodoku/            # Bundled HoDoKu 2.2.0 JAR + launch wrapper (validation only)
docs/              # Architecture, roadmap, reglib status, specs
tests/
├── reglib/        # Technique-isolation regression suite
├── regression/    # Exemplar solve-path suite (requires Java)
└── sdm/           # Broad-variety puzzle suite (requires Java)
```

## Validation approach

Every technique is validated by comparing solve paths against HoDoKu's `/vp` output — same technique type, same cell, same digit, in the same order. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for internals and porting notes.

## License

HoDoKu is GPL-3.0. This port carries the same license.
