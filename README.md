# hodoku-py

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org)
[![PyPI](https://img.shields.io/pypi/v/hodoku-py)](https://pypi.org/project/hodoku-py/)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue)](https://www.gnu.org/licenses/gpl-3.0.html)
[![CI](https://github.com/alexdej/hodoku-py/actions/workflows/ci.yml/badge.svg)](https://github.com/alexdej/hodoku-py/actions/workflows/ci.yml)
[![Nightly](https://github.com/alexdej/hodoku-py/actions/workflows/parity-nightly.yml/badge.svg)](https://github.com/alexdej/hodoku-py/actions/workflows/parity-nightly.yml)
[![flake8](https://alexdej.github.io/hodoku-py/badges/flake8.svg)](https://github.com/alexdej/hodoku-py/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/alexdej/hodoku-py/graph/badge.svg)](https://codecov.io/gh/alexdej/hodoku-py)

A pure Python port of [HoDoKu](https://hodoku.sourceforge.net/) — Sudoku solver, hint engine, puzzle generator, and difficulty rater minus the GUI.

hodoku-py has full fidelity with HoDoKu 2.2.0: exact same solution path and score across all tested puzzles, in pure python (well, a couple small bits in c).

**[Nightly parity test results](https://alexdej.github.io/hodoku-py/)** — head-to-head comparison against HoDoKu across thousands of puzzles.

## Status

Core solver complete through all techniques. Public API (`Solver.solve`, `get_hint`, `rate`) implemented. Puzzle generator implemented with symmetric and pattern-based generation.

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
| Generator | Puzzle generation | ✅ |

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for full details and known gaps.

## Requirements

- Python 3.11+
- (optional) C build tools (build-essential, xcode, or MSVC) to build native extensions that accelerate
  large Mutant fish searches and the backtracking solver used for generation/uniqueness checking.
  Both are optional with pure Python fallbacks. To build: `python setup.py build_ext --inplace`
  (add `--compiler=mingw32` on Windows with MinGW). See [Implementation notes](#implementation-notes) for details.

## Installation

```bash
pip install -e ".[dev]"
```

## Testing

### Unit tests

```bash
pytest -m unit -v
```

### [reglib](tests/reglib/) — HoDoKu's built-in regression suite (~2 min, ~1100 tests)

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

Puzzle files are plain text (one puzzle per line) sourced from [`tests/testdata/`](tests/testdata/).

The full parity suite runs nightly. [Latest results](https://alexdej.github.io/hodoku-py/).

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
└── generator/     # Backtracking solver, uniqueness checker, puzzle generation
    ├── generator.py     # SudokuGenerator — backtracking solver + puzzle generation
    ├── _gen_accel.c      # optional C accelerator for backtracking solver
    └── pattern.py       # GeneratorPattern for pattern-constrained generation

hodoku/            # Bundled HoDoKu 2.2.0 JAR (for validation)
docs/              # Architecture, roadmap, specs
tests/
├── reglib/        # Technique-isolation regression suite (pure Python)
├── parity/        # Head-to-head parity suite (requires Java + py4j)
├── generator/     # Generator unit, integration, and parity tests
└── testdata/      # Puzzle files for parity testing
```

## Validation approach

Every technique is validated by solving the puzzle and comparing the solution with HoDoKu's in detail — same list of techniques, eliminations, and placements, in the same order. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for internals and porting notes.

## Implementation notes

### C accelerators

CPython is ~50-100x slower than Java JIT for tight bitwise loops, so two optional
C extensions accelerate the most performance-sensitive code paths:

- **Fish cover search** (`solver/_fish_accel.c`): The Mutant and Franken variants of the largest Fish
  (Squirmbag, Whale, Leviathan) have enormous search spaces. The cover DFS is implemented in C.
- **Backtracking solver** (`generator/_gen_accel.c`): The backtracking solver used for uniqueness
  checking and puzzle generation runs ~10x faster with the C accelerator.

Both are built via `python setup.py build_ext --inplace` and have pure Python fallbacks.


## Quick demo

```python
from hodoku import Solver, Generator, DifficultyType

# Solve a puzzle
solver = Solver()
result = solver.solve(
    "530070000600195000098000060800060003400803001700020006060000280000419005000080079"
)
print(f"Difficulty: {result.level.name} (score {result.score})")
print(f"Solved in {len(result.steps)} steps")
# Difficulty: EASY (score 204)
# Solved in 51 steps

# Generate a puzzle
gen = Generator()
puzzle = gen.generate(difficulty=DifficultyType.HARD)
print(puzzle)  # 81-char string, 0s for empty cells
```

## Why?

Good question. I was curious whether one could use Claude Code to port a complex code base from java to python. Turns out one could.

## License

HoDoKu is GPL-3.0. This port carries the same license.
