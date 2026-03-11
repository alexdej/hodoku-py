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

HoDoKu JAR lives at `hodoku/hodoku.jar`. Java source at `../HoDoKu/`.

```bash
# Solve a puzzle, print solution path
java -jar hodoku/hodoku.jar /vp /o stdout <puzzle_string>

# Find ALL applicable steps (no solve, richer output)
java -jar hodoku/hodoku.jar /bsa /o stdout <puzzle_string>

# Run regression tester (file path must NOT start with / — it's parsed as an option flag)
cp tests/reglib/reglib-1.3.txt reglib-1.3.txt
java -jar hodoku/hodoku.jar /test reglib-1.3.txt
```

Every technique implementation must be validated against HoDoKu output on the same puzzle.

## Project structure

```
docs/               # ARCHITECTURE.md, ROADMAP.md, specs
hodoku/             # HoDoKu JAR + shell wrapper
src/hodoku/
  core/             # Grid, CellSet, SolutionStep, types, scoring
  solver/           # SudokuStepFinder, all specialized solvers:
                    #   simple, single_digit, wings, coloring, fish,
                    #   uniqueness, chains, tabling, als, misc, brute_force
                    #   (chain_utils, table_entry — shared helpers)
  generator/        # SudokuGenerator (stub — not yet implemented)
  api.py            # public-facing Solver and Generator classes
tests/
  reglib/           # Technique-isolation tests from reglib-1.3.txt (primary validation)
  regression/       # Full solve-path regression tests (exemplars)
pyproject.toml
```

## Implementation status

Done (all validated against HoDoKu — 1106/1112 reglib tests passing, 6 xfail):
- core/ — Grid, CellSet, SolutionStep, types, scoring
- solver/simple.py — Full House, Naked/Hidden Single, Locked Candidates, Subsets
- solver/single_digit.py — Skyscraper, 2-String Kite, Empty Rectangle, Dual variants
- solver/wings.py — XY-Wing, XYZ-Wing, W-Wing
- solver/coloring.py — Simple Colors, Multi-Colors
- solver/fish.py — Basic fish, Finned, Sashimi, Franken, Mutant (all sizes through Whale)
- solver/uniqueness.py — Uniqueness 1-6, Hidden Rectangle, Avoidable Rectangle 1-2, BUG+1
- solver/chains.py — X-Chain, XY-Chain, Remote Pair, Nice Loops, AIC, Grouped variants
- solver/tabling.py — Forcing Chains/Nets, Grouped chains with ALS nodes
- solver/als.py — ALS-XZ, ALS-XY-Wing, ALS-XY-Chain, Death Blossom
- solver/misc.py — Sue de Coq
- solver/templates.py — Template Set, Template Delete
- solver/brute_force.py — last-resort guess
- solver/solver.py — full solve loop, scoring, level computation
- api.py — public Solver API (fully wired; input validation via _validate_puzzle; Generator stubs remain)

Not yet implemented:
- generator/ — puzzle generation
- api.py — wire up Solver/Generator classes to actual implementations

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
- **C accelerator**: `solver/_fish_accel.c` for Mutant fish cover search — a proper Python
  C extension built via `setup.py build_ext --inplace` (add `--compiler=mingw32` on Windows
  with MinGW). Pure Python fallback if not compiled.

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

- **reglib suite** (`tests/reglib/`): Primary validation. 1112 technique-isolation tests from
  HoDoKu's reglib-1.3.txt. Each reconstructs a PM board and checks that `find_all()` returns
  the expected eliminations. Current: 1106 passed / 0 failed / 6 xfail.
- **parity suite** (`tests/parity/`): Secondary validation. Runs each test in the given text file 
  through our solver and HoDoKu.jar and compares the results in detail. Solution must match precisely
  step-by-step
- **exemplar-1.3.txt** (`tests/parity/`): High-priority test from the parity suite. 669 example puzzles
  that exercise all the solution rules. Must match our output exactly.
- **IMPORTANT**: both reglib and exemplar-1.3.txt are long-running test suites. Avoid running the whole
  suite except as necessary to confirm no regressions. Always capture the output for later analysis, and on 
  subsequent runs, run a subset by name using `-k`.


## Python environment

- Python is available directly in the PATH. Run `python` and `pytest` without any wrapper.
- Try to keep use of python commands consistent so that the user has the option to approve each tool once for the whole session. If
  you switch between different python executables the user has to approve each time and that slows us down.

## Source control

- Use **jj** (jujutsu) for commits, not git.
- This is not a collaborative project; all work is on one instance.
