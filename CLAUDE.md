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

## Context

Read the project README.md, docs/ROADMAP.md, and docs/ARCHITECTURE.md before starting any task.

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

Below is an overview of test suites. Also review the available test markers in pyproject.toml

- **unit tests** (`tests/ -m unit/`): Unit-level validation. First level of validation, fast, low coverage.
- **reglib suite** (`tests/reglib/`): Full regression suite. 1112 technique-isolation tests from
  HoDoKu's reglib-1.3.txt. Each reconstructs a PM board and checks that `find_all()` returns
  the expected eliminations. Current: 1106 passed / 0 failed / 6 xfail. Second level of validation, thorough coverage but slow.
- **parity suite** (`tests/parity/`): Compatibility suite. Runs each test in the given text file 
  through our solver and HoDoKu.jar and compares the results in detail. Solution must match precisely
  step-by-step. Runs nightly and builds a report. Typically not run locally except to debug.
- **exemplar-1.3.txt** (`tests/parity/`): The highest priority of the tests in the parity suite. 669 example puzzles
  that exercise all the solution rules. Must match our output exactly. Large/slow. Runs nightly.
- **IMPORTANT**: reglib and most of the parity suites are very long-running. Avoid running the whole
  suite at once except as needed to check for regressions. Use -k to run a subset of test cases.
  If you have to do a full run, save the output to a file so you don't lose it and have to start over.


## Python environment

- Python is available directly in the PATH. Run `python` and `pytest` without any wrapper. User uses docker containers and conda on the host to provide isolation.
- Try to keep use of python commands consistent so that the user has the option to approve each tool once for the whole session. If
  you switch between different python executables the user has to approve each time and that slows us down.

## Source control

- Contributors are expected to commit all changes to a branch and push to origin 
  (which is a locally hosted bare git repo `hodoku-py.git`).
- **IMPORTANT**: check `jj status`. If a `jj` repo is intialized, use the `jj` workflow below
  unless explicitly instructed by the user to use `git`. Otherwise use `git`.

```
# Feature workflow with jj:
jj new -m "description of work in progress"
# ... make changes ...
jj bookmark create my-branch -r @
jj git push --bookmark my-branch

# Feature workflow with git:
git checkout -b my-branch
# ... make changes ...
git add <files>  # don't forget
git commit -m "description of work"
git push -u origin my-branch
```

### Key `jj` concepts
- `@` is your current working copy commit, always exists, never "dirty"
- `@-` is the parent of your working copy
- There is no staging area -- changes are automatically tracked
- Bookmarks are like git branches

### Workflow
- `jj git clone <repo> <dir>` clone an existing repo into dir.
- `jj status` to see working copy changes
- `jj diff` to see what changed
- `jj describe` to modify the current working copy commit
- `jj new` to create a new empty commit as a child of the current commit.
- `jj commit -m "message"` to commit -- equivalent to describe + new
- `jj log` to see history

### Rules
- Always work on a named bookmark. Do not push to `main` unless explicitly requested to do so by the user.
- Always run unit tests before committing.
- Do not push to origin unless asked to by the user (this will depend on context).
- Run reglib suite before pushing to origin, if pushing to origin.

