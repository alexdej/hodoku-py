# Generator Implementation Spec

Port of HoDoKu's puzzle generation system to Python. This spec covers the
backtracking solver (used for uniqueness checking), the full-grid generator,
the clue-removal loop, difficulty-filtered generation, and the pattern system.

## Java source files being ported

| Java class | Python target | Purpose |
|---|---|---|
| `generator/SudokuGenerator.java` | `generator/generator.py` | Backtracking solver + grid gen + clue removal |
| `generator/BackgroundGenerator.java` | `generator/generator.py` | Difficulty-filtered generation loop |
| `generator/GeneratorPattern.java` | `generator/pattern.py` | Pattern constraint for given positions |
| `generator/SudokuGeneratorFactory.java` | *(skip)* | Thread pool — not needed |
| `generator/BackgroundGeneratorThread.java` | *(skip)* | GUI background cache — not needed |

We skip the factory and background thread classes per the project's "no threading"
design decision (see CLAUDE.md).

---

## Architecture overview

Generation in HoDoKu is a three-stage process:

```
Stage 1: Generate a random complete (solved) grid
         → doGenerateFullGrid()

Stage 2: Remove clues from the full grid while preserving uniqueness
         → generateInitPos(symmetric)  OR  generateInitPos(pattern)

Stage 3: Rate the puzzle; if it doesn't match the target difficulty, discard and retry
         → BackgroundGenerator.generate(level, mode)
```

Each stage is described in detail below.

---

## Stage 1: Backtracking solver (`SudokuGenerator`)

### Purpose

The backtracking solver serves two roles:
1. **Uniqueness checking** (`validSolution` / `getNumberOfSolutions`): determine
   whether a puzzle has exactly one solution, and if so, store it.
2. **Full grid generation** (`doGenerateFullGrid`): fill an empty grid with a
   valid random solution.

Both use the same core `solve()` loop — a non-recursive backtracker with an
explicit stack.

### Data structures

```python
@dataclass
class _StackEntry:
    """One level in the backtracking recursion stack."""
    values: list[int]       # cell values (81 ints, 0=empty)
    candidates: list[int]   # per-cell 9-bit candidate masks
    free: list[list[int]]   # [27][10] constraint-digit free counts
    unsolved: int           # count of unsolved cells
    index: int = -1         # cell being branched on at this level
    cands: list[int] = ()   # candidate digits for that cell
    cand_idx: int = 0       # next candidate to try
```

Notes:
- Java uses full `Sudoku2` objects in the stack; we use a lightweight struct
  holding only the three arrays the backtracker needs (`values`, `candidates`,
  `free`) plus `unsolved` count. This mirrors the Java `setBS()` "lightweight
  copy" pattern.
- The stack is pre-allocated with 82 entries (depth 0 = initial state, depth
  1..81 = one per cell guess).
- Singles queues (`ns_queue`, `hs_queue`) are NOT stored in the stack. They are
  rebuilt locally inside `_set_all_exposed_singles()` from the `free` array each
  time, matching the Java approach where `setBS()` clears both queues.

### Core method: `solve()`

The backtracking loop mirrors `SudokuGenerator.solve()` exactly:

```
1. Set stack[0] from the input puzzle state.
2. Propagate all exposed singles on stack[0]. If invalid → solutionCount=0, return.
3. If already solved → record solution, solutionCount=1, return.
4. Main loop:
   a. Find the unsolved cell with fewest candidates (MRV heuristic).
      - Scan cells[0..80]; for each unsolved cell (candidates != 0),
        count bits. Pick the cell with minimum count.
      - Java iterates i=0..80 checking getCell(i)!=0 (candidates mask)
        and ANZ_VALUES[getCell(i)] < best. We do the same with bit_count().
   b. Push to next stack level: record cell index and candidate list.
   c. Inner loop — try each candidate:
      - Copy state from parent level (lightweight copy: values, candidates, free).
      - Place the candidate: update values, candidates for buddies, free counts.
      - Propagate all exposed singles. If valid → break to outer loop.
      - If invalid → try next candidate.
      - If all candidates exhausted → pop back up.
   d. If stack exhausted (level <= 0) → done.
   e. When solved (unsolved == 0):
      - solutionCount++
      - Record first solution.
      - If solutionCount > 1 → return immediately (multiple solutions detected).
```

### `_set_all_exposed_singles()`

Mirrors `SudokuGenerator.setAllExposedSingles()`:

```
1. Build local NS queue: scan all cells, find those with exactly 1 candidate.
2. Build local HS queue: scan free[c][d] for all constraints c, digits d;
   where free[c][d]==1, find the cell and enqueue.
3. Process loop (repeat until both queues empty):
   a. Process all naked singles first:
      - Dequeue (cell, digit). If cell still has that candidate, set it.
      - Setting a cell: update values, remove candidates from buddies,
        update free[] counts. This may enqueue new NS/HS entries.
      - If setting produces a contradiction (buddy already has that value,
        or a constraint has 0 cells for some digit) → return False.
   b. Then process all hidden singles:
      - Same logic.
4. Return True if no contradiction.
```

**Important**: The Java code processes NS before HS in each iteration of the
do-while loop, matching HoDoKu's propagation order. We must do the same.

**Validity detection**: Java's `setCell` returns false when invalid. Our Grid's
`set_cell` doesn't return a boolean. For the generator's internal backtracker,
we implement validity checking directly: after eliminating a candidate from a
buddy, check if that buddy's candidate mask becomes 0 (no candidates left for
an unsolved cell) or if `free[c][d]` becomes 0 for any digit d in any of the
buddy's constraints. Either condition means invalid.

### `_set_cell_bs()` — lightweight cell placement

For the backtracking solver's inner loop, we need a fast cell-set operation that
only updates the three core arrays. This mirrors Java's `setCellBS()`:

```python
def _set_cell_bs(values, candidates, free, cell_constraints, index, value):
    """Set cell value; remove candidate from all buddies; update free counts.

    Returns False if the placement creates a contradiction.
    """
    values[index] = value
    mask = candidates[index]
    candidates[index] = 0
    # Update free[] for all candidates being removed from this cell
    for d in range(1, 10):
        if mask & (1 << (d - 1)):
            for c in cell_constraints[index]:
                free[c][d] -= 1
    # Remove value from all buddies
    digit_mask = 1 << (value - 1)
    buddies = BUDDIES[index]
    while buddies:
        lsb = buddies & -buddies
        j = lsb.bit_length() - 1
        buddies ^= lsb
        if candidates[j] & digit_mask:
            candidates[j] &= ~digit_mask
            for c in cell_constraints[j]:
                free[c][value] -= 1
                if free[c][value] == 0 and values[_find_cell(...)]:
                    ... # contradiction check
            if candidates[j] == 0 and values[j] == 0:
                return False  # cell has no candidates
    return True
```

The actual implementation should be a module-level function (not a method) for
performance, operating on raw lists.

### Public API of the backtracking solver

```python
class SudokuGenerator:
    def valid_solution(self, grid: Grid) -> bool:
        """Check uniqueness; if unique, store solution in grid.solution."""

    def get_number_of_solutions(self, grid: Grid) -> int:
        """Return 0, 1, or 2 (0=invalid, 1=unique, 2=multiple)."""

    def get_solution(self) -> list[int]:
        """Return the first solution found (81-element int array)."""

    def get_solution_as_string(self) -> str:
        """Return the first solution as an 81-char string."""
```

---

## Stage 2a: Full grid generation (`doGenerateFullGrid`)

### Algorithm

1. Create a random permutation of cell indices 0..80 (`generate_indices`).
   - Java: 81 random swaps using `rand.nextInt(81)`.
   - We use `random.Random` for reproducibility (accept optional seed).
2. Start with an empty grid (all cells 0, all candidates 0x1FF).
3. Backtracking loop (same structure as `solve()`):
   - Instead of MRV, pick the next unsolved cell according to
     `generate_indices` order (first unsolved cell in the shuffled order).
   - Try each candidate for that cell.
   - Propagate singles; if valid, advance; if invalid, try next candidate.
4. `actTries` counter: if > 100 backtracks at the top level, return False
   (caller retries with a new random permutation).
5. Caller (`generateFullGrid`) loops `while not doGenerateFullGrid()`.
6. Result stored in `new_full_sudoku: list[int]` (81-element array of values).

### Python implementation note

The random permutation in Java does 81 swaps of random pairs. We must replicate
this exactly if we want seeded reproducibility. However, since the seeds
themselves are random (no fixed seed in Java), exact replication of the shuffle
algorithm is not needed for parity — any valid random permutation works. We can
use `random.shuffle()`.

---

## Stage 2b: Clue removal — symmetric mode (`generateInitPos(symmetric)`)

### Algorithm

Starting from the full grid in `new_full_sudoku`:

1. Copy to `new_valid_sudoku`.
2. `used[81]` = all False; `used_count` = 81; `remaining_clues` = 81.
3. While `remaining_clues > 17` and `used_count > 1`:
   a. Pick a random starting index `i = rand.nextInt(81)`.
   b. Advance `i` to the next un-tried cell:
      `i = (i + 1) % 81` until `not used[i]`. Mark `used[i] = True`.
   c. If `new_valid_sudoku[i] == 0` → already removed, continue.
   d. If `symmetric` and the 180-degree partner is already removed → continue.
      - Symmetric partner of cell at (r,c) = cell at (8-r, 8-c) = `9*(8-i//9) + (8-i%9)`.
      - Exception: center cell (r=4,c=4, index 40) has no partner.
   e. Remove cell `i` (and its symmetric partner if applicable).
   f. Run `solve(new_valid_sudoku)` to check uniqueness.
   g. If `solutionCount > 1` → restore the removed cell(s).
   h. Otherwise, the removal is permanent.
4. Result: `new_valid_sudoku` contains the puzzle with minimum ~17 clues.

### Fidelity note

The cell selection loop in Java uses a scan-forward approach (`i++` with
wrapping and `while(used[i])`), not `random.choice`. We replicate this exactly.

---

## Stage 2c: Clue removal — pattern mode (`generateInitPos(pattern)`)

### Algorithm

1. Copy `new_full_sudoku` to `new_valid_sudoku`.
2. For each cell `i` where `pattern[i] == False`, set `new_valid_sudoku[i] = 0`.
3. Run `solve(new_valid_sudoku)`.
4. If `solutionCount > 1` → return False (caller generates a new full grid and
   retries, up to `MAX_TRIES = 1_000_000`).
5. If unique → return True.

---

## Stage 3: Difficulty-filtered generation (`BackgroundGenerator.generate`)

### Algorithm

This is the outer loop that produces a puzzle at the requested difficulty level:

```
1. Loop up to MAX_TRIES (20,000) iterations:
   a. Generate a random sudoku: creator.generateSudoku(symmetric=True)
      - This runs stages 1 + 2.
   b. Solve the puzzle with the full solver (SudokuSolver.solve).
   c. Check if the puzzle's difficulty matches the target:
      - solved_level.ordinal == target_level.ordinal
      - AND if rejectTooLowScore: score >= previous_level.max_score
   d. If match → return the puzzle string.
   e. Otherwise → continue.
2. If no match found after MAX_TRIES → return None.
```

### Python implementation

We already have `SudokuSolver.solve()` returning a `SolveResult` with `level`
and `score`. The generation loop becomes:

```python
def generate(difficulty: DifficultyType, symmetric: bool = True,
             pattern: list[bool] | None = None,
             max_tries: int = 20_000,
             rng: random.Random | None = None) -> str | None:
    generator = SudokuGenerator(rng=rng)
    solver = SudokuSolver()

    for _ in range(max_tries):
        sudoku = generator.generate_sudoku(symmetric, pattern)
        if sudoku is None:
            return None  # pattern impossible

        result = solver.solve(sudoku)
        if not result.solved:
            continue

        if result.level == difficulty:
            # Also check score is within range (reject too-low scores)
            prev_max = DIFFICULTY_MAX_SCORE.get(
                DifficultyType(difficulty.value - 1), 0
            ) if difficulty.value > 1 else 0
            if result.score >= prev_max:
                return sudoku

    return None  # could not find a puzzle at requested difficulty
```

### GameMode

Java's `BackgroundGenerator` supports three game modes: PLAYING, LEARNING, and
PRACTISING. LEARNING and PRACTISING filter puzzles based on whether they contain
specific "training" steps (technique types marked for practice).

For the initial port, we implement PLAYING mode only. The `generate()` API
accepts only a `DifficultyType`. LEARNING/PRACTISING can be added later if
needed (they require the `enabledTraining` flag on `StepConfig`, which we don't
currently expose).

---

## Module layout

### `generator/generator.py`

```python
"""Puzzle generator — backtracking solver + generation loop."""

class SudokuGenerator:
    """Backtracking solver and puzzle generator.

    Mirrors Java's SudokuGenerator. Provides:
    - Uniqueness checking (validSolution / getNumberOfSolutions)
    - Full grid generation
    - Clue removal (symmetric or pattern-based)
    - Difficulty-filtered generation
    """

    def __init__(self, rng: random.Random | None = None): ...

    # --- Backtracking solver (uniqueness checking) ---
    def valid_solution(self, grid: Grid) -> bool: ...
    def get_number_of_solutions(self, grid: Grid) -> int: ...

    # --- Grid generation ---
    def generate_sudoku(self, symmetric: bool = True,
                        pattern: list[bool] | None = None) -> str | None: ...

    # --- Difficulty-filtered generation ---
    def generate(self, difficulty: DifficultyType,
                 symmetric: bool = True,
                 pattern: list[bool] | None = None,
                 max_tries: int = 20_000) -> str | None: ...

# Module-level helpers (performance-critical, no class overhead):
def _solve_backtrack(values, candidates, free) -> tuple[int, list[int] | None]: ...
def _set_all_exposed_singles(values, candidates, free) -> bool: ...
def _copy_state(values, candidates, free) -> tuple[list, list, list]: ...
```

### `generator/pattern.py`

```python
"""GeneratorPattern — constrain which cells contain givens."""

@dataclass
class GeneratorPattern:
    """Pattern indicating which cells must be givens.

    Attributes:
        name: Human-readable pattern name.
        pattern: 81-element list of bool; True = cell must be a given.
        valid: Whether the pattern has been verified to produce solvable puzzles.
    """
    name: str = ""
    pattern: list[bool] = field(default_factory=lambda: [False] * 81)
    valid: bool = False

    @property
    def num_givens(self) -> int:
        """Count of True entries in pattern."""
        return sum(self.pattern)
```

### Updates to `api.py`

Wire up the `Generator` class:

```python
class Generator:
    def __init__(self, seed: int | None = None) -> None:
        rng = random.Random(seed) if seed is not None else random.Random()
        self._generator = SudokuGenerator(rng=rng)

    def generate(self, difficulty=DifficultyType.MEDIUM,
                 pattern: list[int] | None = None) -> str:
        # Convert pattern from list[int] (cell indices) to list[bool]
        bool_pattern = None
        if pattern is not None:
            bool_pattern = [False] * 81
            for idx in pattern:
                bool_pattern[idx] = True

        result = self._generator.generate(difficulty, pattern=bool_pattern)
        if result is None:
            raise RuntimeError("Could not generate puzzle at requested difficulty")
        return result

    def validate(self, puzzle: str) -> Literal["valid", "invalid", "multiple"]:
        _validate_puzzle(puzzle)
        grid = Grid()
        grid.set_sudoku(puzzle)
        count = self._generator.get_number_of_solutions(grid)
        if count == 0:
            return "invalid"
        elif count == 1:
            return "valid"
        else:
            return "multiple"
```

---

## Existing code integration

### Grid changes needed

The current `Grid.set_cell()` does not return a validity boolean. The generator's
internal backtracker should NOT use `Grid` at all — it operates on raw lists for
performance. The backtracker is self-contained with its own state management.

The `Grid` class is used only at the boundaries:
- `valid_solution(grid)` reads `grid.values` to initialize the backtracker, then
  writes `grid.solution` on success.
- `generate_sudoku()` returns a puzzle string (not a Grid).

### Solver integration

The difficulty-filtered `generate()` method uses `SudokuSolver.solve()` directly.
No changes to the solver are needed.

### BruteForceSolver

Already checks `grid.solution` and uses it if set. The `valid_solution()` call
in the solve loop (documented in ARCHITECTURE.md) populates `grid.solution`,
which `BruteForceSolver` then uses as a shortcut. This integration point already
exists and requires no changes.

---

## Performance considerations

The backtracking solver is the hottest code path — it's called once per clue-
removal attempt (typically 30-60 times per puzzle), and once per generate-and-
rate iteration (potentially thousands of times for hard difficulty targets).

### Optimization strategy

1. **Raw lists, not Grid objects**: The backtracker operates on plain `list[int]`
   for values, candidates, and free counts. No `Grid` allocation per stack level.

2. **Lightweight copy**: `_copy_state()` copies only the three arrays needed
   (values: 81 ints, candidates: 81 ints, free: 27*10 ints = 270 ints). Total:
   432 ints per stack level. Use `list()` constructor for copies (fastest in CPython).

3. **Inline singles propagation**: The `_set_all_exposed_singles()` function
   does not create Grid objects or use deque — it uses local lists as queues.

4. **Bit operations**: Use `bit_count()` for candidate counting, `& -x` for
   LSB extraction — same patterns used throughout the solver.

5. **Pre-computed tables**: `BUDDIES`, `CELL_CONSTRAINTS`, `DIGIT_MASKS` are
   already module-level constants in `grid.py`.

### Expected performance

Java generates + rates a puzzle in ~1-3ms. Python will be ~50-100x slower for
the backtracker, so ~50-300ms per solve. A difficulty-filtered generation loop
might need 100-1000 iterations for HARD/UNFAIR, so total generation time:
~5-300 seconds. This is acceptable for a library (not interactive GUI).

If performance proves unacceptable, the backtracking solver is an excellent
candidate for a C accelerator following the `_fish_accel.c` pattern.

---

## Testing strategy

### Unit tests (`tests/test_generator.py`)

1. **Backtracking solver correctness**:
   - Known puzzle with unique solution → `valid_solution` returns True,
     `grid.solution` matches expected.
   - Puzzle with multiple solutions → returns False.
   - Invalid puzzle (contradiction in givens) → returns 0 solutions.
   - Already-solved grid → returns True, solution = grid.

2. **Full grid generation**:
   - Generated grid is valid (all houses contain 1-9).
   - Generated grid is complete (no empty cells).
   - Two calls with different seeds produce different grids.

3. **Clue removal (symmetric)**:
   - Resulting puzzle has unique solution.
   - Resulting puzzle is 180-degree symmetric (non-center clues have partners).
   - Has between 17 and ~35 clues.

4. **Clue removal (pattern)**:
   - Clues appear only at pattern-True positions.
   - If pattern is achievable, puzzle has unique solution.

5. **Difficulty-filtered generation**:
   - Generated EASY puzzles rate as EASY.
   - Generated MEDIUM puzzles rate as MEDIUM.
   - Generated HARD puzzles rate as HARD.
   - `max_tries=0` returns None.

### Parity tests (optional, lower priority)

Since generation is random, we can't do step-by-step parity with HoDoKu. But
we can verify:
- Our `valid_solution` agrees with Java's on a corpus of known puzzles.
- Our difficulty rating of generated puzzles matches when solved by both engines.

---

## Task breakdown for implementation

Each task below is designed to be completed by a single agent session.

### Task 1: Backtracking solver core

**File**: `src/hodoku/generator/generator.py`

Implement:
- `_StackEntry` dataclass
- `_copy_state()` helper
- `_set_all_exposed_singles()` — propagate NS/HS from raw arrays
- `_solve_backtrack()` — the main backtracking loop
- `SudokuGenerator.valid_solution(grid)`
- `SudokuGenerator.get_number_of_solutions(grid)`
- `SudokuGenerator.get_solution()` / `get_solution_as_string()`

Tests:
- Known unique puzzle → solution count = 1, correct solution stored.
- Multi-solution puzzle → solution count = 2.
- Invalid puzzle → solution count = 0.
- Already-solved grid → solution count = 1.
- Empty grid → solution count = 2 (many solutions).

Reference: `SudokuGenerator.solve()` and `setAllExposedSingles()` in
`SudokuGenerator.java` lines 210-638.

### Task 2: Full grid generation + symmetric clue removal

**File**: `src/hodoku/generator/generator.py`

Implement:
- `SudokuGenerator._do_generate_full_grid()` — random-order backtracking fill
- `SudokuGenerator._generate_full_grid()` — retry wrapper
- `SudokuGenerator._generate_init_pos_symmetric()` — symmetric clue removal
- `SudokuGenerator.generate_sudoku(symmetric, pattern=None)` — returns puzzle string

Tests:
- Full grid: valid, complete, all houses correct.
- Symmetric puzzle: unique solution, 180-degree symmetric, >= 17 clues.
- Seeded RNG: same seed → same grid (deterministic).

Reference: `doGenerateFullGrid()` (lines 408-499), `generateInitPos(boolean)`
(lines 540-596), `generateSudoku()` (lines 352-387) in `SudokuGenerator.java`.

### Task 3: Pattern-based clue removal + GeneratorPattern

**Files**: `src/hodoku/generator/generator.py`, `src/hodoku/generator/pattern.py`

Implement:
- `GeneratorPattern` dataclass in `pattern.py`
- `SudokuGenerator._generate_init_pos_pattern(pattern)` — pattern-based removal
- Wire pattern into `generate_sudoku(symmetric, pattern)`

Tests:
- Pattern with ~25 givens: puzzle has clues only at True positions.
- Pattern that can't produce unique puzzle after MAX_TRIES: returns None.
- `GeneratorPattern.num_givens` property.

Reference: `generateInitPos(boolean[])` (lines 510-530), `GeneratorPattern.java`.

### Task 4: Difficulty-filtered generation + API wiring

**Files**: `src/hodoku/generator/generator.py`, `src/hodoku/api.py`

Implement:
- `SudokuGenerator.generate(difficulty, symmetric, pattern, max_tries)` — the
  generate-and-rate loop
- Update `api.py` `Generator` class: wire `generate()` and `validate()`
- Update `generator/__init__.py` exports

Tests:
- `Generator().generate(DifficultyType.EASY)` produces valid EASY puzzle.
- `Generator().generate(DifficultyType.MEDIUM)` produces valid MEDIUM puzzle.
- `Generator().validate(known_unique)` → "valid".
- `Generator().validate(known_multi)` → "multiple".
- `Generator().validate(known_invalid)` → "invalid".
- Seeded generator: same seed + same difficulty → same puzzle.

Reference: `BackgroundGenerator.generate()` in `BackgroundGenerator.java` lines
90-160.

### Task 5: Integration testing + solver integration

**Files**: `tests/test_generator.py`, solver integration

Implement:
- Verify `valid_solution` is called in the solve loop (if not already wired).
- End-to-end: generate puzzle → solve it → verify steps are correct.
- Benchmark: time the generation loop for each difficulty level.
- Verify BruteForceSolver correctly uses `grid.solution` from generator.

This task also addresses any integration issues found during tasks 1-4.

---

## Appendix: Java ↔ Python naming map

| Java | Python | Notes |
|------|--------|-------|
| `SudokuGenerator` | `SudokuGenerator` | Same name |
| `BackgroundGenerator` | *(merged into SudokuGenerator.generate)* | No separate class needed |
| `GeneratorPattern` | `GeneratorPattern` | Same name |
| `validSolution(Sudoku2)` | `valid_solution(Grid) -> bool` | |
| `getNumberOfSolutions(Sudoku2)` | `get_number_of_solutions(Grid) -> int` | |
| `generateSudoku(boolean)` | `generate_sudoku(symmetric) -> str` | Returns string, not Grid |
| `doGenerateFullGrid()` | `_do_generate_full_grid() -> bool` | Private |
| `generateInitPos(boolean)` | `_generate_init_pos_symmetric()` | Private |
| `generateInitPos(boolean[])` | `_generate_init_pos_pattern(pattern)` | Private |
| `setAllExposedSingles(Sudoku2)` | `_set_all_exposed_singles(v, c, f)` | Module-level fn |
| `BackgroundGenerator.generate(level, mode)` | `SudokuGenerator.generate(difficulty, ...)` | |
| `SudokuGeneratorFactory` | *(skip)* | No threading |
| `BackgroundGeneratorThread` | *(skip)* | No GUI |
| `RecursionStackEntry` | `_StackEntry` | Private dataclass |
| `newFullSudoku` | `_full_grid` | Instance attribute |
| `newValidSudoku` | `_puzzle_grid` | Instance attribute |
| `MAX_TRIES` (pattern) | `MAX_PATTERN_TRIES = 1_000_000` | |
| `MAX_TRIES` (background) | `max_tries` parameter (default 20_000) | |
| `GameMode.PLAYING` | *(default, only mode)* | LEARNING/PRACTISING deferred |
