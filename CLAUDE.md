# hodoku-py

Python port of HoDoKu's algorithmic core: solver, hint engine, puzzle generator. No GUI.
Goal is 100% fidelity to HoDoKu.

## What we're building

A Python library. Public API surface:

```python
from hodoku import Solver, Generator, DifficultyType

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
bash hodoku/hodoku.sh /vp /o stdout <puzzle_string>

# Find ALL applicable steps (no solve, richer output)
bash hodoku/hodoku.sh /bsa /o stdout <puzzle_string>
```

Every technique implementation must be validated against HoDoKu output on the same puzzle.

**Note on Git Bash (Windows):** hodoku.jar's `/flag` arguments get mangled into Windows paths by
Git Bash. Prefix commands with `MSYS_NO_PATHCONV=1` if running under Git Bash. This is already
baked into `hodoku/hodoku.sh` but matters if invoking `java -jar` directly.

## Project structure

```
docs/               # CODEBASE_MAP.md, ARCHITECTURE.md — reference these before coding
hodoku/             # HoDoKu JAR
src/
  hodoku/        # the library
    core/           # Grid, CellSet, SolutionStep, types, scoring
    solver/         # SudokuSolver, SudokuStepFinder, all specialized solvers
    generator/      # SudokuGenerator, pattern support
    api.py          # public-facing Solver and Generator classes
tests/
pyproject.toml
```

## HoDoKu source code

HoDoKu source code is available for reference at `../HoDoKu` (relative to the project directory).

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

## A note on porting approach and trade-offs

- IMPORTANT! We are targeting 100% fidelity with HoDoKu down to the smallest detail of ordering. In general
  when porting code, favor exact behavior matches: sort and enumerate items in the same order, set
  MIN and MAX constants the same, and so on. There might be times where the HoDoKu code seems sub-optimal
  but keep in mind that the goal of this port is fidelity, not optimization. Two solve paths that
  would be equivalent from a Sudoku perspective will fail the regression suite.

## HoDoKu compatibility rule: elimination ordering

When a technique finds candidate eliminations, **always add them to the
`SolutionStep` in ascending cell-index order** (`sorted(cells)`).  Java's
`SudokuSet` is ordered, so `addCandidateToDelete` is always called
lowest-index first.  The order matters because `del_candidate` feeds
`hs_queue`: the first elimination hits the queue first and determines which
hidden single fires next.  Getting this wrong causes solve-path divergence.
Full details in `docs/ROADMAP.md` → "HoDoKu compatibility: elimination ordering".

## Testing approach

- Unit-test each solver in isolation with puzzle strings where that technique is the next step
- Compare full solution paths against HoDoKu batch output for regression
- Benchmark suite separate from correctness tests
- The goal is 100% fidelity with HoDoKu, down to the precise step-by-step solve path, even if a different
  solve path would be equivalent (or better). This project is a strict port of HoDoKu as it stands, not an attempt
  to improve or optimize it. Maintaining strict step-by-step fidelity simplifies validation.
