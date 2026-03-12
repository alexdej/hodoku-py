# hodoku-py Architecture

Python port of HoDoKu's solver, hint engine, and generator — no GUI.

---

## Reference implementation

HoDoKu JAR is checked in at `hodoku/hodoku.jar`. [Source code mirror @ github](https://github.com/alexdej/HoDoKu)

```bash
# Solve a puzzle, print solution path
java -Xmx512m -jar hodoku/hodoku.jar /vp /o stdout <puzzle_string>

# Find ALL applicable steps (no solve, richer output)
java -Xmx512m -jar hodoku/hodoku.jar /bsa /o stdout <puzzle_string>

# Run regression tester
java -Xmx512m -jar hodoku/hodoku.jar /test tests/reglib/reglib-1.3.txt

# NOTE: file paths cannot start with '/' or they will be parsed as option flags. 
# Unfortunate legacy of app being developed on windows. Workaround: always use relative paths.
```


## Module breakdown

```
hodoku/
├── __init__.py
├── api.py                  # Public-facing library API
├── core/
│   ├── __init__.py
│   ├── grid.py             # Grid state (≈ Sudoku2)
│   ├── cell_set.py         # SudokuSet — 81-cell bitset
│   ├── solution_step.py    # SolutionStep + supporting types
│   ├── types.py            # SolutionType, SolutionCategory enums
│   └── scoring.py          # StepConfig, DifficultyLevel, DifficultyType
├── solver/
│   ├── __init__.py
│   ├── step_finder.py      # SudokuStepFinder — central hub + cache
│   ├── solver.py           # SudokuSolver — solve loop + rating
│   ├── simple.py           # Singles, locked candidates, subsets
│   ├── fish.py             # All fish variants
│   ├── single_digit.py     # Skyscraper, 2-String Kite, Empty Rectangle
│   ├── uniqueness.py       # Uniqueness Tests, BUG+1, Hidden/Avoidable Rect
│   ├── wings.py            # XY-Wing, XYZ-Wing, W-Wing
│   ├── coloring.py         # Simple Colors, Multi-Colors
│   ├── chains.py           # X-Chain, XY-Chain, Remote Pair, Nice Loop/AIC
│   ├── als.py              # ALS-XZ, ALS-XY-Wing, ALS-XY-Chain, Death Blossom, SDC
│   ├── tabling.py          # Forcing Chains/Nets, Grouped Nice Loop/AIC
│   ├── templates.py        # Template Set/Delete
│   └── brute_force.py      # Last-resort guess
└── generator/
    ├── __init__.py
    ├── generator.py        # Backtracking solver + puzzle generation
    └── pattern.py          # GeneratorPattern for pattern-constrained generation
```

---

## Key data structures

### Grid (`core/grid.py`)

```python
@dataclass
class Grid:
    # Primary state
    values: list[int]          # len=81, 0=empty, 1-9=placed digit
    candidates: list[int]      # len=81, 9-bit mask (bit i-1 = digit i present)
    solution: list[int]        # len=81, filled by generator after validation

    # Derived (recomputed on mutation, or lazily)
    is_solved: bool
    unsolved_count: int

    # Static lookup tables — identical to Java, computed once at module load
    LINES: ClassVar[list[list[int]]]    # [9][9] row cell indices
    COLS:  ClassVar[list[list[int]]]    # [9][9] col cell indices
    BLOCKS: ClassVar[list[list[int]]]   # [9][9] box cell indices
    ALL_UNITS: ClassVar[list[list[int]]] # [27][9] all houses
    CONSTRAINTS: ClassVar[list[list[int]]] # [81][3] → [row, col, box]
    BUDDIES: ClassVar[list[int]]        # [81] each as int bitmask (81-bit)
    LINE_TEMPLATES: ClassVar[list[int]] # [9] each as int bitmask
    COL_TEMPLATES: ClassVar[list[int]]  # [9]
    BLOCK_TEMPLATES: ClassVar[list[int]] # [9]
```

**Candidate mask encoding:** bit `i-1` represents digit `i`.
`mask & (1 << (d-1)) != 0` → digit d is a candidate in that cell.

**Key methods:**
```python
def set_cell(self, index: int, value: int) -> None
def del_candidate(self, index: int, digit: int) -> None
def get_candidates_list(self, index: int) -> list[int]
def set_sudoku(self, puzzle_string: str) -> None   # parse 81-char string
def get_sudoku_string(self) -> str
def clone(self) -> "Grid"
```

### Cell Bitset (`core/cell_set.py`)

The Java `SudokuSet` is a 128-bit value split across two `long` fields. In Python, `int` is arbitrary precision — use a single `int` directly.

```python
class CellSet:
    """81-cell bitset. Wraps a Python int for portability but uses
    bit operations directly for performance-critical paths."""

    _bits: int   # bit i = cell i is in set

    def add(self, index: int) -> None:   self._bits |=  (1 << index)
    def remove(self, index: int) -> None: self._bits &= ~(1 << index)
    def contains(self, index: int) -> bool: return bool(self._bits >> index & 1)
    def is_empty(self) -> bool:          return self._bits == 0
    def size(self) -> int:               return self._bits.bit_count()
    def and_(self, other: "CellSet") -> "CellSet"
    def or_(self, other: "CellSet") -> "CellSet"
    def and_not(self, other: "CellSet") -> "CellSet"
    def __iter__(self) -> Iterator[int]  # yields set indices low→high

    # Static precomputed buddy masks (plain ints, computed once)
    BUDDIES: ClassVar[list[int]]         # BUDDIES[i] = int bitmask of 20 buddies
```

For inner loops, use raw `int` operations instead of `CellSet` methods where profiling shows it matters.

### Solution step (`core/solution_step.py`)

```python
@dataclass
class SolutionStep:
    type: SolutionType
    # What to do
    indices: list[int] = field(default_factory=list)  # cells to set
    values:  list[int] = field(default_factory=list)  # values for those cells
    candidates_to_delete: list[Candidate] = field(default_factory=list)
    # Hint explanation metadata
    entity: int = 0             # house type (ROW/COL/BOX/CELL)
    entity_number: int = 0
    entity2: int = 0
    entity2_number: int = 0
    base_entities: list[Entity] = field(default_factory=list)
    cover_entities: list[Entity] = field(default_factory=list)
    fins: list[Candidate] = field(default_factory=list)
    endo_fins: list[Candidate] = field(default_factory=list)
    chains: list[Chain] = field(default_factory=list)
    alses: list[AlsInStep] = field(default_factory=list)
    restricted_commons: list[RestrictedCommon] = field(default_factory=list)
    color_candidates: dict[int, int] = field(default_factory=dict)
    # Scoring
    progress_score: int = -1
    progress_score_singles: int = -1

@dataclass(frozen=True)
class Candidate:
    index: int   # cell index 0-80
    value: int   # digit 1-9

@dataclass(frozen=True)
class Entity:
    type: int    # Grid.ROW / Grid.COL / Grid.BOX / Grid.CELL
    number: int  # 1-based
```

### Chain encoding (`core/chain.py`)

Mirrors Java's `Chain` bit-packed int format exactly — required for correct `TablingSolver` behavior. A chain is a `list[int]` where each entry is a 32-bit packed value:

```
bits  0- 3: candidate (digit)
bit       4: 1=strong link, 0=weak link
bits  5-11: cell index 1 (or ALS entry cell)
bits 12-18: cell index 2 (group node 2nd cell, or lower 7 bits of ALS index)
bits 19-25: cell index 3 (group node 3rd cell, or upper 7 bits of ALS index)
bits 26-29: node type (0=normal, 1=group, 2=ALS)
```

Provide static helper functions mirroring `Chain.makeSEntry()`, `Chain.getSCellIndex()`, etc.

### ALS structures (`solver/als.py`)

```python
@dataclass
class Als:
    indices: CellSet         # cells in this ALS
    candidates: int          # 9-bit mask of digits present
    indices_per_candidate: list[CellSet]   # [10] cells holding each candidate
    buddies_per_candidate: list[CellSet]   # [10] external cells seeing all ALS cells with cand
    buddies_als_per_candidate: list[CellSet] # [10] above + the ALS cells themselves
    buddies: CellSet         # union of buddies_per_candidate

@dataclass
class RestrictedCommon:
    als1: int    # index into ALS list
    als2: int
    cand1: int   # first RC candidate
    cand2: int   # second RC candidate (0 if none)
    actual_rc: int  # 0-3, which RC(s) are active

@dataclass
class GroupNode:
    indices: CellSet
    buddies: CellSet
    cand: int
    line: int    # -1 if not applicable
    col: int
    block: int
    index1: int
    index2: int
    index3: int  # -1 if 2-cell node
```

---

## Public API (`api.py`)

```python
# api.py — the only import users need

from hodoku.api import Solver, Generator, SolutionType, DifficultyType

class Solver:
    def solve(self, puzzle: str) -> SolveResult:
        """
        Solve a puzzle string (81 chars, '.' or '0' for empty).
        Returns steps, difficulty level, and score.
        Raises ValueError if puzzle is invalid or has no unique solution.
        """

    def get_hint(self, puzzle: str) -> SolutionStep | None:
        """Return the next logical step, or None if solved."""

    def rate(self, puzzle: str) -> RatingResult:
        """Return difficulty level and score without full solution path."""

    def find_all_steps(self, puzzle: str) -> list[SolutionStep]:
        """Return every applicable technique at the current state."""

@dataclass
class SolveResult:
    solved: bool
    steps: list[SolutionStep]
    level: DifficultyType       # EASY / MEDIUM / HARD / UNFAIR / EXTREME
    score: int
    solution: str               # 81-char solved grid string

@dataclass
class RatingResult:
    level: DifficultyType
    score: int

class Generator:
    def generate(
        self,
        difficulty: DifficultyType = DifficultyType.MEDIUM,
        pattern: list[int] | None = None,   # fixed clue positions (0-80)
    ) -> str:
        """Generate a puzzle string at the requested difficulty."""

    def validate(self, puzzle: str) -> Literal["valid", "invalid", "multiple"]:
        """Check uniqueness of a puzzle."""
```

**Usage example:**
```python
from hodoku.api import Solver, Generator, DifficultyType

solver = Solver()
result = solver.solve("530070000600195000098000060800060003400803001700020006060000280000419005000080079")
print(result.level)    # DifficultyType.EASY
print(result.score)    # e.g. 196
for step in result.steps:
    print(step.type.name, step.indices, step.values)

hint = solver.get_hint("530070000...")
print(hint.type.name)  # "NAKED_SINGLE"

gen = Generator()
puzzle = gen.generate(difficulty=DifficultyType.HARD)
```

---

## Solver internal flow

```
Solver.solve(puzzle_str)
  └─ Grid.set_sudoku(puzzle_str)
  └─ SudokuGenerator.valid_solution(grid)   # validate uniqueness, store solution
  └─ loop:
       SudokuStepFinder.get_step(type) for each StepConfig in order
       → if found: SudokuStepFinder.do_step(step), accumulate score/level
       → if GIVE_UP emitted: stop
  └─ return SolveResult
```

`SudokuStepFinder` lazy-initializes each specialized solver and caches per-step-number data:
- `candidates[1..9]` — `CellSet` of cells where digit d is still a candidate
- `positions[1..9]` — `CellSet` of cells where digit d is placed
- `als_list` — all found ALS objects (invalidated each step)
- `rc_list` — all restricted commons (invalidated each step)
- `templates[1..9]` — valid placement templates per digit

---

## Implementation strategy

Implement in this sequence — each layer depends only on those above it:

| Phase | Module(s) | What it unlocks |
|---|---|---|
| 1 | `core/cell_set.py` | All bitset operations |
| 2 | `core/types.py` | SolutionType, SolutionCategory enums |
| 3 | `core/grid.py` | Full grid with static tables, set_cell, del_candidate |
| 4 | `core/solution_step.py` | SolutionStep and all sub-types |
| 5 | `core/scoring.py` | StepConfig, DifficultyLevel defaults |
| 6 | `generator/generator.py` | Backtracking solver + validSolution |
| 7 | `solver/step_finder.py` | Skeleton: candidate cache, getStep dispatch |
| 8 | `solver/solver.py` | Solve loop, scoring, level computation |
| 9 | `solver/simple.py` | Full House, Naked/Hidden Single, Locked Candidates, Subsets |
| 10 | `solver/single_digit.py` | Skyscraper, 2-String Kite, Empty Rectangle |
| 11 | `solver/wings.py` | XY-Wing, XYZ-Wing, W-Wing |
| 12 | `solver/coloring.py` | Simple Colors, Multi-Colors |
| 13 | `solver/uniqueness.py` | Uniqueness Tests 1-6, BUG+1 |
| 14 | `solver/fish.py` | Basic fish, then finned/franken/mutant (can be done incrementally) |
| 15 | `solver/chains.py` | X-Chain, XY-Chain, Remote Pair, simple Nice Loop |
| 16 | `core/chain.py` + `solver/als.py` | ALS data structures + ALS-XZ/XY-Wing/XY-Chain |
| 17 | `solver/tabling.py` | Forcing Chains, Forcing Nets, Grouped chains (hardest) |
| 18 | `solver/templates.py` | Template Set/Delete |
| 19 | `solver/brute_force.py` | Last-resort guess |
| 20 | `api.py` | Public API surface |
| 21 | `generator/pattern.py` | Pattern-constrained generation |

### Validation strategy at each phase

After phase 9 (SimpleSolver), the Python output can be compared against HoDoKu batch mode for all Easy puzzles:

```bash
bash hodoku/hodoku.sh /vp /o stdout <puzzle>
python -m hodoku <puzzle>
# compare step-by-step
```

After each subsequent phase, extend the test corpus to include puzzles requiring that technique.

---

## Porting notes

### What maps cleanly
- All static tables in `Sudoku2` → Python module-level constants (tuples/lists)
- `SudokuSet` (two longs) → Python `int` (arbitrary precision, no wrapper needed)
- `SolutionStep` → `@dataclass` with same fields
- `SolutionType` enum → Python `Enum` with `(name, library_code, arg_name)` values
- `StepConfig[]` sorted array → Python `list[StepConfig]` with a default config constant

### What needs care
- **Candidate bitmasks in `Sudoku2`**: Java uses `short` (16-bit signed). In Python use plain `int` and mask with `0x1FF` when needed.
- **`SudokuSinglesQueue`**: The inline propagation loop inside `set_cell` is performance-critical. Keep as a plain list/deque, not a class initially.
- **`TablingSolver` bit packing in `TableEntry`**: `retIndices` are 64-bit longs with packed fields. Use Python `int` and the same bit masks verbatim.
- **`Options` singleton**: Replace with a `SolverConfig` dataclass with a `DEFAULT_CONFIG` constant. No global mutable state.
- **Threading** (`SudokuSolverFactory`, `SudokuGeneratorFactory`): Skip for the initial port; use simple factory functions.
- **Performance**: The Java code relies heavily on `int[]` array operations and bitwise ops. Python is ~10-50× slower for these. Profile after the correctness baseline is established; accelerate with `numpy` bitsets or C extensions only where needed.

### Candidate representation decision

Java `Sudoku2` stores candidates as `short[81]` (9-bit masks per cell), plus `SudokuSet[10]` (per-digit bitsets of which cells have that candidate). **Both are maintained simultaneously.**

The Python port must do the same: `candidates: list[int]` (per cell) and `candidate_sets: list[int]` (per digit, each a CellSet int) — keep them in sync inside `set_cell()` and `del_candidate()`.

### C accelerator (`_fish_accel.c`)

The Mutant fish cover-combination search has a huge search space (up to C(24,6) = 134K
base combos × cover DFS for Whale). CPython is ~50-100x slower than Java JIT for tight
bitwise loops, making this intractable in pure Python.

`solver/_fish_accel.c` implements the cover DFS in C, loaded via `ctypes` at import time.
81-bit candidate masks are split into lo/hi `uint64` halves (matching Java's M1/M2).

When installed from source, the `.c` file *should* be compiled, but is allowed
to fail with a warning. If the binary is not found at runtime, the code falls back
to pure python. There is no harm in doing so, other than poor performance on certain
mutant fish patterns (very rare in the wild, but present in the test suite).

If more hot loops need C acceleration in the future, follow the same pattern:
self-contained `.c` file, Python fallback.

### Subtle ordering bugs

Many of our hardest-to-fix parity bugs involved ordering of candidates or steps. 
Pay close attention to the ordering of items returned from collections, and look
out for java methods that should be stateless but actually change the order of 
an underlying collection. In several places in the code we explicitly normalize
collection iteration to match java's, and there are a handful of places where we
don't but have commented that it's a potential risk. In order to achieve 100%
parity, internal ordering of every data structure must match.

