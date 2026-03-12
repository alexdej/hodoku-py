# hodoku-py

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue)](https://www.gnu.org/licenses/gpl-3.0.html)
[![CI](https://github.com/alexdej/hodoku-py/actions/workflows/ci.yml/badge.svg)](https://github.com/alexdej/hodoku-py/actions/workflows/ci.yml)
[![Nightly](https://github.com/alexdej/hodoku-py/actions/workflows/parity-nightly.yml/badge.svg)](https://github.com/alexdej/hodoku-py/actions/workflows/parity-nightly.yml)
[![Parity](https://alexdej.github.io/hodoku-py/badges/exemplars-1.0.svg)](https://alexdej.github.io/hodoku-py/)

A pure Python port of [HoDoKu](https://hodoku.sourceforge.net/) — Sudoku solver, hint engine, and difficulty rater minus the GUI.

hodoku-py has full fidelity with HoDoKu 2.2.0: exact same solution path and score across all tested puzzles, in pure python (well, one small bit in c).

## Status

Core solver complete through all techniques. Public API (`Solver.solve`, `get_hint`, `rate`) implemented. Puzzle generator not yet implemented.

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
| Forcing chains/nets | Contradiction + Verity | ✅ |
| Misc | Sue de Coq | ✅ |
| Templates | Template Set/Delete | ✅ |
| Public API | `Solver.solve`, `get_hint`, `rate`, `find_all_steps` | ✅ |
| Generator | Puzzle generation | ⬜ |

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for full details and known gaps.

## Requirements

- Python 3.11+
- (optional) C build tools (build-essential, xcode, or MSVC) to build a native extension that accelerates the search
  for certain large Mutant fish patterns. The extension is optional but without it, certain tests in `reglib/` will be skipped.
  To build: `python setup.py build_ext --inplace` (add `--compiler=mingw32` on Windows with MinGW).

## Installation

```bash
pip install -e ".[dev]"
```

## Testing

### Unit tests (fast, pure Python)

```bash
pytest -m unit -v
```

### [reglib](tests/reglib/) — HoDoKu's built-in regression suite (~2 min, ~1100 tests, pure Python)

Each test reconstructs a fixed pencilmark board and asserts that one specific technique fires with the expected eliminations.

```bash
pytest tests/reglib/ -q

# Single technique by code
pytest tests/reglib/ -k "0901" -v

# Technique family
pytest tests/reglib/ --reglib-section 09 -v
```

### [parity](tests/parity/) — head-to-head HoDoKu comparison (requires Java JRE installation)

Comparison of full solution solve path against HoDoKu.jar via [Py4J](https://www.py4j.org/).

```bash
pytest tests/parity/ --puzzle-file exemplars-1.0 -v
pytest tests/parity/ --puzzle-file top1465 --puzzle-count 50 --puzzle-seed 7 -v
```

Puzzle files are plain text (one puzzle per line) sourced from `tests/testdata/`.

### Skip the tests that require Java

```bash
pytest tests/ -m "not java"   # pure-Python tests only
```

## CI

| Workflow | Trigger | What it does |
|----------|---------|-------------|
| **CI** | push/PR to main | Unit tests (Python 3.11–3.13) → Reglib suite |
| **Parity** | manual / nightly | Full solve-path comparison per puzzle file |
| **Parity (ad-hoc)** | manual | Single puzzle file with optional count/seed |

## Project structure

```
src/hodoku/
├── core/          # Grid, CellSet, SolutionStep, enums, scoring
├── solver/        # One file per technique family + central dispatcher
│   ├── step_finder.py   # SudokuStepFinder — routes get_step() calls
│   ├── solver.py        # SudokuSolver — solve loop and difficulty rating
│   ├── simple.py        # Singles, locked candidates, subsets
│   ├── fish.py          # Basic, finned/sashimi, Franken, Mutant fish
│   ├── _fish_accel.c    # optional C accelerator for Mutant fish
│   ├── single_digit.py  # Skyscraper, 2-String Kite, Empty Rectangle
│   ├── uniqueness.py    # Uniqueness Tests 1–6, BUG+1
│   ├── wings.py         # XY-Wing, XYZ-Wing, W-Wing
│   ├── coloring.py      # Simple Colors, Multi-Colors
│   ├── chains.py        # X-Chain, XY-Chain, Nice Loop / AIC families
│   ├── tabling.py       # Forcing Chains/Nets
│   ├── als.py           # ALS-XZ, ALS-XY-Wing, ALS-XY-Chain, Death Blossom
│   ├── misc.py          # Sue de Coq
│   └── templates.py     # Template Set/Delete
└── generator/     # Not yet implemented

hodoku/            # Bundled HoDoKu 2.2.0 JAR (validation only)
docs/              # Architecture, roadmap, specs
tests/
├── reglib/        # Technique-isolation regression suite (pure Python)
├── parity/        # Head-to-head parity suite (requires Java + py4j)
└── testdata/      # Puzzle files for parity testing
```

## Validation approach

Every technique is validated by solving the puzzle and comparing the solution with HoDoKu's in detail — same list of techniques, eliminations, and placements, in the same order. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for internals and porting notes.


## Why?

Good question. I was curious whether one could use Claude Code to port a complex code base from java to python. Turns out one could. 

## License

HoDoKu is GPL-3.0. This port carries the same license.
