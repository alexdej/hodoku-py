# Spec: GUI Views

Notes on which hodoku-py API outputs feed each view in a HoDoKu-clone GUI.
All views are achievable by sorting/grouping the data already returned —
no new return types are needed.

---

## Step text formatting

`str(step)` produces the minimal HoDoKu-style format (`Hidden Single: r5c8=4`,
`Locked Candidates Type 2 (Claiming): r2c2<>7`).  The GUI uses a richer format
for multi-cell techniques that separates pattern cells from eliminations:

```
Locked Triple: 2,8,9 in r456c7 => r139c7,r56c8,r6c9<>2, ...
Naked Triple: 4,5,9 in r7c13,r9c2 => r8c3,r9c1<>4, ...
Hidden Pair: 6,7 in r6c34 => r6c3<>1, r6c3<>2, ...
```

All data needed for this format is present in `SolutionStep` fields (`values`,
`indices`, `candidates_to_delete`).  A GUI will need its own richer formatter
on top of `str(step)` — that's a GUI concern, not an engine concern.

---

## Summary tab

A table of technique counts and total score for a solved puzzle.

**Source:** `SolveResult` from `solver.solve(puzzle)`

```python
from collections import Counter
counts = Counter(step.type for step in result.steps)
total_score = result.score
level = result.level
```

---

## Solution path tab

Step-by-step solution in HoDoKu format (`Hidden Single: r5c8=4`).

**Source:** `SolveResult.steps`, formatted via `str(step)` (already implemented).

---

## All possible steps tab

Five views of `find_all_steps()` results, all achievable by sorting/grouping
the returned `list[SolutionStep]` on the client side.

| View | Sort/group key |
|---|---|
| By type | `step.type` |
| By row/col | First cell index in `step.indices` or `step.candidates_to_delete` |
| By eliminations | Placements first (any count beats any elimination), then by `len(step.candidates_to_delete)` descending; steps with identical elimination sets are grouped together |
| By directly unlocked singles | `step.progress_score_singles_only` descending |
| By unlocked singles | `step.progress_score_singles` descending |

The "directly unlocked singles" view has a three-level tree (confirmed from
GUI screenshot):

```
Directly Unlocked Singles: 24
  Resulting Score: 20506
    Almost Locked Set XZ-Rule: A=r7c1 {45}, ...
    Hidden Triple: 1,7,9 in r8c3,r9c12 ...
  Resulting Score: 20526
    ...
Directly Unlocked Singles: 23
  ...
```

"Resulting Score" is `step.progress_score` — the sum of base scores of all
steps needed to complete the puzzle after applying this step.  It is populated
by `find_all_steps()` via `getProgressScore()`.  No separate field is needed.

### Progress score fields

Java's `FindAllSteps.run()` unconditionally calls `SudokuSolver.getProgressScore()`
as its final phase (step 27 in the switch) — there is no opt-in.  Our
`find_all_steps()` must do the same: always populate all three fields by
tentatively applying each step to a scratch grid and solving forward.

`SudokuSolver.getProgressScore()` uses a dedicated `solverStepsProgress` step
list (a cheaper subset of the full solver steps) rather than the full solve
order — we will need a corresponding constant when porting.

### `progress_score` fields on SolutionStep

| Field | Meaning |
|---|---|
| `progress_score` | Sum of base scores of all steps needed to complete the puzzle after applying this step — this is the "Resulting Score" shown in the GUI tree |
| `progress_score_singles` | Count of singles unlocked transitively after applying this step |
| `progress_score_singles_only` | Count of singles unlocked *directly* (one step ahead only) |

No separate `resulting_score` field is needed: `progress_score` is that value.
All three fields default to `-1` on `SolutionStep`; `solve()` does not populate
them — only `find_all_steps()` does.

---

## Search for Backdoors dialog

A backdoor set is a minimal set of cells or candidates that, once revealed or
eliminated, reduces the remainder of the puzzle to singles only.  The depth
(number of candidates) controls how large the set is — depth 1 means a single
revealed digit collapses the puzzle, depth 2 requires a pair, and so on.
Puzzles with no depth-1 backdoor are "genuinely hard" in a way that puzzles
with one are not, even if both require advanced techniques.

**Proposed API:**

```python
from hodoku import Solver, BackdoorResult

results = solver.find_backdoors(
    puzzle,
    search_cells=True,       # search for cell backdoors (set correct value)
    search_candidates=False, # search for candidate backdoors (eliminate candidate)
    depth=1,                 # backdoor set size
)
# returns list[BackdoorResult]
```

`BackdoorResult` fields (TBD when porting — derive from `BackdoorSearchDialog.java`):
- `cells`: the backdoor set as cell indices + values (for cell backdoors) or
  `Candidate` objects (for candidate backdoors)
- `singles_score`: how many singles are unlocked (used for "Results for Singles" column)
- `progress_score`: progress measure score (used for "Results for Progress Measure" column)

**Java source:** `sudoku/BackdoorSearchDialog.java` — in scope to port.
