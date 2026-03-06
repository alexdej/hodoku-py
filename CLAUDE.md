# hodoku-py

Python port of HoDoKu's algorithmic core: solver, hint engine, puzzle generator. No GUI.

## What we're building

A Python library. Public API surface:

```python
from hodoku_py import Solver, Generator, DifficultyType

solver = Solver()
result = solver.solve("530070000...")   # returns steps, level, score
hint   = solver.get_hint("530070000...") # returns next SolutionStep or None
rating = solver.rate("530070000...")    # returns level + score only

gen = Generator()
puzzle = gen.generate(difficulty=DifficultyType.MEDIUM)
```

## Reference implementation

HoDoKu JAR lives at `hodoku/hodoku.jar`. Run it with:

```bash
# Solve a puzzle, print solution path
MSYS_NO_PATHCONV=1 bash hodoku/hodoku.sh /vp /o stdout <puzzle_string>

# Find ALL applicable steps (no solve, richer output)
MSYS_NO_PATHCONV=1 bash hodoku/hodoku.sh /bsa /o stdout <puzzle_string>
```

Every technique implementation must be validated against HoDoKu output on the same puzzle.

## Project structure

```
docs/               # CODEBASE_MAP.md, ARCHITECTURE.md — reference these before coding
hodoku/             # HoDoKu JAR + Java source (read-only reference)
src/
  hodoku_py/        # the library
    core/           # Grid, CellSet, SolutionStep, types, scoring
    solver/         # SudokuSolver, SudokuStepFinder, all specialized solvers
    generator/      # SudokuGenerator, pattern support
    api.py          # public-facing Solver and Generator classes
tests/
pyproject.toml
```

## Implementation order

Build in this sequence — each layer depends only on those above:

1. `core/cell_set.py` — 81-cell bitset (Python int)
2. `core/types.py` — SolutionType, SolutionCategory enums
3. `core/grid.py` — Grid with static lookup tables, set_cell, del_candidate
4. `core/solution_step.py` — SolutionStep dataclass and sub-types
5. `core/scoring.py` — StepConfig, DifficultyLevel defaults
6. `generator/generator.py` — backtracking solver + uniqueness validation
7. `solver/step_finder.py` — SudokuStepFinder skeleton + candidate cache
8. `solver/solver.py` — solve loop, scoring, level computation
9. `solver/simple.py` — Full House, Naked/Hidden Single, Locked Candidates, Subsets
   **→ first validation checkpoint against HoDoKu**
10. `solver/single_digit.py` — Skyscraper, 2-String Kite, Empty Rectangle
11. `solver/wings.py` — XY-Wing, XYZ-Wing, W-Wing
12. `solver/coloring.py` — Simple Colors, Multi-Colors
13. `solver/uniqueness.py` — Uniqueness Tests 1-6, BUG+1
14. `solver/fish.py` — Basic fish first, then finned/franken/mutant incrementally
15. `solver/chains.py` — X-Chain, XY-Chain, Remote Pair, simple Nice Loop/AIC
16. `solver/als.py` — ALS-XZ, ALS-XY-Wing, ALS-XY-Chain, Death Blossom, SDC
17. `solver/tabling.py` — Forcing Chains/Nets, Grouped chains (hardest)
18. `solver/templates.py` — Template Set/Delete
19. `solver/brute_force.py` — last-resort guess
20. `api.py` — public API wrapping SudokuSolver

## Key design decisions

- **CellSet**: Python `int` as 81-bit bitset — simpler than Java's two-long split
- **Candidates**: maintain TWO parallel structures (same as Java):
  - `grid.candidates[i]` — per-cell 9-bit mask (bit d-1 = digit d present)
  - `grid.candidate_sets[d]` — per-digit CellSet (which cells have digit d)
  - Keep in sync inside `set_cell()` and `del_candidate()`
- **Options singleton**: replaced by `SolverConfig` dataclass with a `DEFAULT_CONFIG` constant
- **No threading**: skip SudokuSolverFactory/SudokuGeneratorFactory pools for now
- **Chain encoding**: use same 32-bit bit-packed int format as Java (required for TablingSolver)
- **Static tables**: `Sudoku2`'s lookup arrays → module-level constants in `core/grid.py`

## Testing approach

- Unit-test each solver in isolation with puzzle strings where that technique is the next step
- Compare full solution paths against HoDoKu batch output for regression
- Test corpus lives in `tests/puzzles/` as text files (one puzzle per line)
- Benchmark suite separate from correctness tests
