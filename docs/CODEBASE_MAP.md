# HoDoKu Codebase Map

Source: `hodoku/HoDoKu/src/` — Java 6, HoDoKu v2.2.0 (2012)
Scope legend: **IN** = port this, **OUT** = skip (GUI/config/printing)

---

## Package: `sudoku` — Core data structures, enums, and GUI

### IN-SCOPE

| Class | Responsibility | Key in-scope dependencies |
|---|---|---|
| `Sudoku2` | The grid. 81-cell array of values (int[81]) and candidates (short[81] bitmasks). Pre-computes static lookup tables for rows/cols/blocks/buddies. Owns a `SudokuSinglesQueue`. Central mutable state for everything. | `SudokuSinglesQueue`, `SudokuSet`, `SudokuGenerator` (for validation) |
| `SudokuSet` | 81-bit bitset for tracking which cells match a predicate (e.g. "cells where digit 5 is a candidate"). Extends `SudokuSetBase`. Adds iteration (get(i)) and set-theoretic ops (and/or/andNot). | `SudokuSetBase` |
| `SudokuSetBase` | Base bitset: two `long` fields (mask1: bits 0-63, mask2: bits 64-80) with add/remove/contains/isEmpty/and/or/andNot. | — |
| `SudokuSetShort` | Narrower bitset variant (fits in one long). Used internally for unit templates. | — |
| `SudokuSinglesQueue` | Bounded queue (int[243]) detecting Naked/Hidden Singles during candidate propagation in `Sudoku2.setCell()`/`delCandidate()`. Avoids re-scanning all cells. | `Sudoku2` |
| `SolutionStep` | One hint result: technique type, cell indices to set, candidates to delete, house entities, chains, ALS references, coloring info, fish fins/endo-fins, progress scores. | `SolutionType`, `Chain`, `Als`, `AlsInSolutionStep`, `Candidate`, `Entity`, `RestrictedCommon` |
| `SolutionType` | Enum of ~75 technique names (Full House through Multi-Colors 2). Each carries a display name, library code, and arg-name. Methods: `isSingle()`, `isFish()`, `getStepConfig()`, `compare()`. | `StepConfig`, `Options` |
| `SolutionCategory` | Enum grouping techniques: Singles, Intersections, Subsets, Fish (6 variants), Single Digit Patterns, Coloring, Uniqueness, Chains and Loops, Wings, Almost Locked Sets, Enumerations, Miscellaneous, Last Resort. | — |
| `StepConfig` | Configuration for one technique: search order index, `SolutionType`, difficulty level index, `SolutionCategory`, `baseScore`, enabled flag, allStepsEnabled flag, progress-mode flags. Owned in `Options.solverSteps[]`. | `SolutionType`, `SolutionCategory`, `DifficultyLevel` |
| `DifficultyLevel` | A difficulty band: `DifficultyType`, `maxScore`, display name, GUI colors. | `DifficultyType` |
| `DifficultyType` | Enum: INCOMPLETE, EASY, MEDIUM, HARD, UNFAIR, EXTREME. | — |
| `Chain` | Bit-packed int array encoding a logic chain. Each 32-bit entry stores: candidate (4 bits), strong/weak flag, cell index (7 bits), optional 2nd/3rd cell or ALS index, node type (normal/group/ALS). Static factory and accessor methods. | `Als`, `TableEntry`, `TablingSolver` |
| `AlsInSolutionStep` | Lightweight reference to an ALS inside a `SolutionStep` (cell set + candidate bitmask). Separate from `Als` to avoid circular dep. | — |
| `Candidate` | (cellIndex, value) pair. Used in `SolutionStep.candidatesToDelete` and related lists. | — |
| `Entity` | (type, number) pair representing a house in a hint description (e.g. "row 3", "box 5"). | — |
| `SudokuStatus` | Enum: VALID, INVALID, MULTIPLE_SOLUTIONS. Returned by generator validation. | — |
| `SudokuUtil` | Static utilities: clear step lists, parse puzzle strings, format output. | — |
| `FindAllSteps` | Runnable that collects every applicable `SolutionStep` for the current grid state (used by `/bsa` batch mode). Delegates to `SudokuStepFinder`. | `SudokuStepFinder`, `SudokuSolverFactory` |
| `Options` | Global singleton. Owns `solverSteps[]` (ordered `StepConfig` array), `solverStepsProgress[]`, `difficultyLevels[]`, and all tuning knobs. Referenced everywhere via `Options.getInstance()`. | `StepConfig`, `DifficultyLevel` |
| `Main` | Entry point. Parses CLI args, calls `batchSolve()`. Contains `BatchSolveThread` (inner class). | `SudokuSolver`, `SudokuGenerator` |
| `RegressionTester` | Batch regression test harness — runs solver against known puzzles. | `SudokuSolver`, `Sudoku2` |
| `ClipboardMode` | Enum for puzzle-string formats (CLUES_ONLY, VALUES_ONLY, LIBRARY, etc.). Used when serializing/deserializing grids. | — |

### OUT-OF-SCOPE (GUI)

All classes extending `javax.swing.*`, implementing `Printable`, or whose names contain Dialog/Frame/Panel/Renderer/DragAndDrop/Image — skip these entirely:

`MainFrame`, `SudokuPanel`, `CellZoomPanel`, `SolutionPanel`, `AllStepsPanel`, `SummaryPanel`, `SplitPanel`, `AboutDialog`, `BackdoorSearchDialog`, `ConfigDialog`, `ConfigColorPanel`, `ConfigColorkuPanel`, `ConfigFindAllStepsPanel`, `ConfigGeneralPanel`, `ConfigGeneratorPanel`, `ConfigLevelFontPanel`, `ConfigProgressPanel`, `ConfigSolverPanel`, `ConfigStepPanel`, `ConfigTrainigPanel`, `ConfigTrainingDialog`, `ExtendedPrintDialog`, `ExtendedPrintProgressDialog`, `PrintSolutionDialog`, `WriteAsPNGDialog`, `FindAllStepsProgressDialog`, `GenerateSudokuProgressDialog`, `SolverProgressDialog`, `FishChooseCandidatesDialog`, `HistoryDialog`, `RestoreSavePointDialog`, `SetGivensDialog`, `KeyboardLayoutFrame`, `SudokuConsoleFrame`, `CheckNode`, `CheckRenderer`, `ColorKuImage`, `ListDragAndDrop`, `ListDragAndDropChange`, `MyBrowserLauncher`, `MyFontChooser`, `NumbersOnlyDocument`, `GeneratorPatternPanel`, `StatusColorPanel`, `GuiState`, `GameMode`

---

## Package: `solver` — All specialized solvers

All classes here are **IN-SCOPE**.

| Class | Responsibility | Key dependencies |
|---|---|---|
| `AbstractSolver` | Base class for all specialized solvers. Two abstract methods: `getStep(SolutionType)` → finds and returns the next applicable step; `doStep(SolutionStep)` → applies the step to the grid. Holds ref to `SudokuStepFinder` and `Sudoku2`. | `SudokuStepFinder`, `Sudoku2` |
| `SudokuStepFinder` | Central hub. Owns one instance of every specialized solver (lazy-init). Caches per-step-number data: candidate sets, position sets, ALS list, Restricted Commons list, template sets. Dispatches `getStep(type)` and `doStep(step)` calls to the right solver. | All `AbstractSolver` subclasses, `Sudoku2`, `SudokuSet` |
| `SudokuSolver` | Orchestrator. Iterates `Options.solverSteps[]` in order calling `stepFinder.getStep(type)` until the puzzle is solved or GIVE_UP. Accumulates score and level. Exposes `solve()`, `getHint()`, `doStep()`. | `SudokuStepFinder`, `Options`, `DifficultyLevel` |
| `SudokuSolverFactory` | Thread-safe pool of `SudokuSolver` instances. Single `defaultSolver` for main use; `getInstance()`/`giveBack()` for background threads. Background cleanup thread. | `SudokuSolver` |
| `SimpleSolver` | Techniques: Full House, Hidden Single, Naked Single, Locked Candidates Types 1&2, Locked Pair/Triple, Naked Pair/Triple/Quad, Hidden Pair/Triple/Quad. Uses `SudokuSinglesQueue` for singles propagation. Caches steps between calls. | `Sudoku2`, `SudokuSinglesQueue`, `SudokuSet` |
| `FishSolver` | All fish patterns: Basic (X-Wing, Swordfish, Jellyfish, up to Leviathan/size 7), Finned, Sashimi, Franken, Finned-Franken, Mutant, Finned-Mutant, Kraken Fish. ~1800 lines. Uses unit template iteration over rows/cols/blocks. | `Sudoku2`, `SudokuSet`, `SolutionStep` |
| `SingleDigitPatternSolver` | Single-digit patterns: Skyscraper, 2-String Kite, Turbot Fish, Empty Rectangle, Dual 2-String Kite, Dual Empty Rectangle. | `Sudoku2`, `SudokuSet` |
| `UniquenessSolver` | Uniqueness Tests 1-6, BUG+1, Hidden Rectangle, Avoidable Rectangle Types 1&2. All require the puzzle to have a unique solution. | `Sudoku2`, `SudokuSet` |
| `WingSolver` | XY-Wing, XYZ-Wing, W-Wing. | `Sudoku2`, `SudokuSet` |
| `ColoringSolver` | Simple Colors (Trap/Wrap), Multi-Colors (Types 1&2). Uses graph coloring over strong links. | `Sudoku2`, `SudokuSet` |
| `ChainSolver` | Simple chain/loop techniques: X-Chain, XY-Chain, Remote Pair, Nice Loop/AIC, Continuous/Discontinuous Nice Loop. Does not use tabling (no implications table). | `Sudoku2`, `SudokuSet`, `Chain` |
| `AlsSolver` | Almost Locked Set techniques: ALS-XZ, ALS-XY-Wing, ALS-XY-Chain, Death Blossom, Sue de Coq. Uses cached ALS and RC lists from `SudokuStepFinder`. | `SudokuStepFinder`, `Als`, `RestrictedCommon`, `SudokuSet` |
| `MiscellaneousSolver` | Currently handles Sue de Coq and other miscellaneous eliminations not covered elsewhere. | `Sudoku2`, `SudokuSet` |
| `TablingSolver` | Table-based chaining: Forcing Chain (Contradiction/Verity), Forcing Net (Contradiction/Verity), Grouped Nice Loop/AIC. Builds on/off implication tables (`TableEntry[][]`) and expands them. Largest solver at ~3200 lines. | `TableEntry`, `Chain`, `GroupNode`, `Als`, `SudokuStepFinder` |
| `TemplateSolver` | Template elimination: Template Set (AND of all valid templates → forced placements), Template Delete (OR complement → impossible candidates). Uses precomputed template lists from `SudokuStepFinder`. | `SudokuStepFinder`, `SudokuSet` |
| `BruteForceSolver` | Last-resort guess. Gets the puzzle solution from `SudokuGenerator.validSolution()` then places the middle unsolved cell. | `SudokuGeneratorFactory`, `Sudoku2` |
| `IncompleteSolver` | Stub emitting `INCOMPLETE` step when puzzle cannot be solved with enabled techniques. | — |
| `GiveUpSolver` | Stub emitting `GIVE_UP` step — terminates the solve loop. | — |
| `Als` | ALS data object: `SudokuSet indices`, `short candidates` (bitmask), per-candidate index sets, per-candidate buddy sets. `computeFields(finder)` populates buddy sets after construction. | `SudokuSet`, `SudokuStepFinder` |
| `RestrictedCommon` | RC between two ALS: indices (als1, als2) into an ALS list, up to two RC candidates (cand1, cand2), actualRC for chain propagation. | `Als` |
| `GroupNode` | 2-3 cells sharing the same candidate, row/col, and block — used as grouped chain nodes. `getGroupNodes(finder)` scans all lines×blocks. | `Sudoku2`, `SudokuSet` |
| `TableEntry` | Implication table row for `TablingSolver`. Parallel arrays: `entries[]` (packed chain nodes), `retIndices[]` (back-pointers + distance, 64-bit), `onSets[]`/`offSets[]` (summary bitsets). | `Chain`, `SudokuSet` |

---

## Package: `generator` — Puzzle generation

| Class | Scope | Responsibility | Key dependencies |
|---|---|---|---|
| `SudokuGenerator` | **IN** | Bit-based backtracking solver (Dancing Links-style). `validSolution(sudoku)` checks uniqueness and stores solution. `generate()` creates full random boards then removes clues while maintaining uniqueness. Uses `SudokuSinglesQueue` for constraint propagation during generation. | `Sudoku2`, `SudokuSinglesQueue` |
| `SudokuGeneratorFactory` | **IN** | Pool of `SudokuGenerator` instances (same pattern as `SudokuSolverFactory`). `getDefaultGeneratorInstance()` for main use. | `SudokuGenerator` |
| `GeneratorPattern` | **IN** | Describes which cells must be givens in a generated puzzle (pattern-constrained generation). | — |
| `BackgroundGenerator` | **PARTIAL** | Manages a pool of pre-generated puzzles. Core logic is in-scope; references to GUI progress dialogs are out-of-scope. | `BackgroundGeneratorThread`, `SudokuGenerator` |
| `BackgroundGeneratorThread` | **IN** | Worker thread that generates puzzles using `SudokuSolver` to rate difficulty. No GUI dependency. | `SudokuGenerator`, `SudokuSolver` |

---

## Key static data in `Sudoku2`

The following pre-computed tables are critical to port (all static, computed once at class load):

| Table | Type | Contents |
|---|---|---|
| `LINES[9][9]` | int[][] | Cell indices for each row |
| `COLS[9][9]` | int[][] | Cell indices for each column |
| `BLOCKS[9][9]` | int[][] | Cell indices for each 3×3 box |
| `ALL_UNITS[27][9]` | int[][] | All 27 houses (9 rows + 9 cols + 9 boxes) |
| `CONSTRAINTS[81][3]` | int[][] | For each cell: [row_index, col_index, box_index] |
| `buddies[81]` | SudokuSet[] | 20-cell buddy set for each cell (same row/col/box, excluding self) |
| `LINE_TEMPLATES[9]` | SudokuSet[] | Bitset of all cells in each row (for bitset intersection ops) |
| `COL_TEMPLATES[9]` | SudokuSet[] | Bitset of all cells in each column |
| `BLOCK_TEMPLATES[9]` | SudokuSet[] | Bitset of all cells in each box |
| `MASKS[10]` | short[] | Bit masks for digits 1-9 in candidate shorts |
| `POSSIBLE_VALUES[512]` | int[][] | For each 9-bit mask: array of set digits |
| `ANZ_VALUES[512]` | int[] | Popcount for each 9-bit mask |
| `CAND_FROM_MASK[512]` | short[] | Lowest set bit → digit |

---

## Summary statistics

- **Total Java source files:** 97
- **In-scope files:** ~35 (all of `solver/`, most of `generator/`, ~20 from `sudoku/`)
- **Out-of-scope files:** ~62 (GUI, printing, config panels)
- **Largest in-scope file:** `TablingSolver.java` (3190 lines) — hardest to port
- **Next largest:** `FishSolver.java` (1828 lines), `Sudoku2.java` (2662 lines)
