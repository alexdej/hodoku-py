"""Backtracking solver and puzzle generator.

Port of Java's ``SudokuGenerator`` — a bit-based backtracking solver that uses
the Grid's naked-single / hidden-single queues to propagate constraints during
search.  Used by the generator to:

* Check uniqueness (``valid_solution`` / ``get_number_of_solutions``).
* Produce the solution array stored on the Grid.
* Generate full grids and derive puzzles by symmetric clue removal.

Reference: ``generator/SudokuGenerator.java`` lines 40–747.
"""

from __future__ import annotations

import random

from hodoku.core.grid import (
    ALL_UNIT_MASKS,
    BUDDIES,
    CELL_CONSTRAINTS,
    DIGIT_MASKS,
    Grid,
    LENGTH,
)

# ---------------------------------------------------------------------------
# Optional C accelerator
# ---------------------------------------------------------------------------

try:
    from hodoku.generator import _gen_accel
    _gen_accel.init_tables(
        list(BUDDIES),
        list(CELL_CONSTRAINTS),
        list(ALL_UNIT_MASKS),
    )
except ImportError:
    _gen_accel = None

# ---------------------------------------------------------------------------
# Precomputed lookup: candidate-mask → list of digits present
# ---------------------------------------------------------------------------

_POSSIBLE_VALUES: tuple[tuple[int, ...], ...] = tuple(
    tuple(d for d in range(1, 10) if mask & (1 << (d - 1)))
    for mask in range(0x200)
)


# ---------------------------------------------------------------------------
# Stack entry for iterative backtracking
# ---------------------------------------------------------------------------

class _StackEntry:
    """One level of the recursion stack."""

    __slots__ = ("grid", "index", "candidates", "cand_index")

    def __init__(self) -> None:
        self.grid: Grid = Grid()
        self.index: int = 0
        self.candidates: tuple[int, ...] = ()
        self.cand_index: int = 0


# ---------------------------------------------------------------------------
# Grid helpers – validity-returning cell placement for the backtracker
# ---------------------------------------------------------------------------

def _del_cand_valid(grid: Grid, index: int, digit: int) -> bool:
    """Remove *digit* as a candidate from *index*.

    Returns ``False`` if the cell is left with **zero** candidates (invalid).
    Otherwise propagates hidden/naked-single queue entries and returns ``True``.
    """
    mask = DIGIT_MASKS[digit]
    if not (grid.candidates[index] & mask):
        return True  # already absent – nothing to do

    grid.candidates[index] &= ~mask
    if grid.candidates[index] == 0:
        return False  # cell has no candidates left → invalid

    grid.candidate_sets[digit] &= ~(1 << index)

    for c in CELL_CONSTRAINTS[index]:
        grid.free[c][digit] -= 1
        if grid.free[c][digit] == 1:
            rem = grid.candidate_sets[digit] & ALL_UNIT_MASKS[c]
            if rem:
                cell = (rem & -rem).bit_length() - 1
                grid.hs_queue.append((cell, digit))
        # Note: Java also deletes stale HS entries when free==0.
        # Python handles staleness via the validity check in
        # _set_all_exposed_singles before processing each queue entry.

    remaining = grid.candidates[index]
    if remaining != 0 and (remaining & (remaining - 1)) == 0:
        # Exactly one candidate left → naked single
        grid.ns_queue.append((index, remaining.bit_length()))

    return True


def _set_cell_valid(grid: Grid, index: int, value: int) -> bool:
    """Place *value* in *index*, propagate constraints.

    Returns ``False`` if the puzzle becomes invalid (a buddy loses its last
    candidate, or a constraint has zero cells left for a digit).

    Mirrors ``Sudoku2.setCell(index, value, false, false)`` —
    ``isFixed=false``, ``user=false``.
    """
    if grid.values[index] == value:
        return True

    valid = True
    grid.values[index] = value

    # --- Step 1: eliminate *value* from every buddy ---
    # Note: we do NOT short-circuit when valid becomes False. Java's setCell
    # also continues removing candidates from all buddies even after a
    # contradiction is found. This matches Java's behavior but means we do
    # unnecessary work after hitting contradictions. Potential optimization
    # target if backtracker performance becomes an issue.
    buddies = BUDDIES[index]
    while buddies:
        lsb = buddies & -buddies
        j = lsb.bit_length() - 1
        buddies ^= lsb
        if not _del_cand_valid(grid, j, value):
            valid = False

    # --- Step 2: clear all remaining candidates from this cell ---
    old_mask = grid.candidates[index]
    grid.candidates[index] = 0
    for d in range(1, 10):
        if old_mask & DIGIT_MASKS[d]:
            grid.candidate_sets[d] &= ~(1 << index)
            for c in CELL_CONSTRAINTS[index]:
                grid.free[c][d] -= 1
                if grid.free[c][d] == 1 and d != value:
                    rem = grid.candidate_sets[d] & ALL_UNIT_MASKS[c]
                    if rem:
                        cell = (rem & -rem).bit_length() - 1
                        grid.hs_queue.append((cell, d))
                elif grid.free[c][d] == 0 and d != value:
                    valid = False

    return valid


def _copy_state(dst: Grid, src: Grid) -> None:
    """Fast state copy for the backtracker (mirrors ``Sudoku2.setBS``).

    Copies values, candidates, candidate_sets, free; clears queues.
    Does **not** copy solution or givens (not needed during search).
    """
    dst.values[:] = src.values
    dst.candidates[:] = src.candidates
    dst.candidate_sets[:] = src.candidate_sets
    dst.free = [list(row) for row in src.free]
    dst.ns_queue.clear()
    dst.hs_queue.clear()


def _set_all_exposed_singles(grid: Grid) -> bool:
    """Drain the naked-single and hidden-single queues.

    Returns ``False`` if the puzzle becomes invalid during propagation.
    Mirrors ``SudokuGenerator.setAllExposedSingles()``.
    """
    valid = True
    ns_queue = grid.ns_queue
    hs_queue = grid.hs_queue

    while True:
        # First all naked singles
        while valid and ns_queue:
            index, value = ns_queue.popleft()
            if grid.candidates[index] & DIGIT_MASKS[value]:
                valid = _set_cell_valid(grid, index, value)

        # Then all hidden singles
        while valid and hs_queue:
            index, value = hs_queue.popleft()
            if grid.candidates[index] & DIGIT_MASKS[value]:
                valid = _set_cell_valid(grid, index, value)

        if not valid or (not ns_queue and not hs_queue):
            break

    return valid


# ---------------------------------------------------------------------------
# SudokuGenerator
# ---------------------------------------------------------------------------

class SudokuGenerator:
    """Bit-based backtracking solver for generation and uniqueness checking."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._stack: list[_StackEntry] = [_StackEntry() for _ in range(82)]
        self._solution: list[int] = [0] * LENGTH
        self._solution_count: int = 0
        self._rand: random.Random = rng if rng is not None else random.Random()
        self._generate_indices: list[int] = list(range(LENGTH))
        self._new_full_sudoku: list[int] = [0] * LENGTH
        self._new_valid_sudoku: list[int] = [0] * LENGTH

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def valid_solution(self, grid: Grid) -> bool:
        """Return ``True`` if *grid* has exactly one solution.

        If unique, the solution is stored on the grid via
        ``grid.set_solution()``.
        """
        self._solve_grid(grid)
        unique = self._solution_count == 1
        if unique:
            grid.set_solution(list(self._solution))
        return unique

    def get_number_of_solutions(self, grid: Grid) -> int:
        """Return 0 (invalid), 1 (unique), or 2 (multiple solutions).

        If unique, the solution is stored on the grid.
        """
        self._solve_grid(grid)
        if self._solution_count == 1:
            grid.set_solution(list(self._solution))
        return self._solution_count

    def get_solution(self) -> list[int]:
        """Return the first solution found by the last solve call."""
        return list(self._solution)

    def get_solution_count(self) -> int:
        """Return the solution count from the last solve call."""
        return self._solution_count

    def get_solution_as_string(self) -> str:
        """Return the solution as an 81-character digit string."""
        return "".join(str(d) for d in self._solution)

    # ------------------------------------------------------------------
    # Puzzle generation
    # ------------------------------------------------------------------

    def generate_sudoku(
        self,
        symmetric: bool = True,
        pattern: list[bool] | None = None,
    ) -> str | None:
        """Generate a new puzzle and return it as an 81-character string.

        If *pattern* is given, uses a fixed given-pattern (may return ``None``
        if no valid puzzle is found in MAX_TRIES attempts).  Otherwise uses
        random symmetric clue removal.

        Mirrors ``SudokuGenerator.generateSudoku(boolean, boolean[])``.
        """
        MAX_PATTERN_TRIES = 1_000_000

        if pattern is None:
            self._generate_full_grid()
            self._generate_init_pos(symmetric)
        else:
            ok = False
            for attempt in range(MAX_PATTERN_TRIES):
                self._generate_full_grid()
                if self._generate_init_pos_pattern(pattern):
                    ok = True
                    break
            if not ok:
                return None

        return "".join(str(d) for d in self._new_valid_sudoku)

    def _generate_full_grid(self) -> None:
        """Retry wrapper for full-grid generation.

        Mirrors ``SudokuGenerator.generateFullGrid()``.
        """
        while not self._do_generate_full_grid():
            pass

    def _do_generate_full_grid(self) -> bool:
        """Generate a random full sudoku grid via backtracking.

        Mirrors ``SudokuGenerator.doGenerateFullGrid()``.  Cells are visited
        in a random order.  If more than 100 backtrack levels are explored,
        the attempt is aborted and the caller retries with a new shuffle.
        """
        act_tries = 0
        rand = self._rand
        indices = self._generate_indices

        # Fisher–Yates-style shuffle (Java's pairwise-swap variant)
        max_len = len(indices)
        for i in range(max_len):
            indices[i] = i
        for i in range(max_len):
            idx1 = rand.randrange(max_len)
            idx2 = rand.randrange(max_len)
            while idx1 == idx2:
                idx2 = rand.randrange(max_len)
            indices[idx1], indices[idx2] = indices[idx2], indices[idx1]

        # Start with empty grid
        stack = self._stack
        stack[0].grid.__init__()
        level = 0
        stack[0].index = -1

        while True:
            if stack[level].grid.values.count(0) == 0:
                # Full grid generated
                self._new_full_sudoku[:] = stack[level].grid.values
                return True

            # Find first unsolved cell in random order
            index = -1
            vals = stack[level].grid.values
            for i in range(LENGTH):
                act_try = indices[i]
                if vals[act_try] == 0:
                    index = act_try
                    break

            level += 1
            stack[level].index = index
            stack[level].candidates = _POSSIBLE_VALUES[
                stack[level - 1].grid.candidates[index]
            ]
            stack[level].cand_index = 0

            # Limit backtracking depth
            act_tries += 1
            if act_tries > 100:
                return False

            # Try candidates at this level
            done = False
            while True:
                while stack[level].cand_index >= len(stack[level].candidates):
                    level -= 1
                    if level <= 0:
                        done = True
                        break
                if done:
                    break

                next_cand = stack[level].candidates[stack[level].cand_index]
                stack[level].cand_index += 1

                _copy_state(stack[level].grid, stack[level - 1].grid)

                if not _set_cell_valid(
                    stack[level].grid, stack[level].index, next_cand
                ):
                    continue

                if _set_all_exposed_singles(stack[level].grid):
                    break

            if done:
                break

        return False

    def _generate_init_pos(self, is_symmetric: bool) -> None:
        """Remove clues from a full grid to create a puzzle.

        Mirrors ``SudokuGenerator.generateInitPos(boolean)``.
        Scan-forward random cell selection with 180-degree symmetry.
        """
        max_pos_to_fill = 17  # minimum 17 givens
        used = [False] * 81
        used_count = 81
        rand = self._rand

        full = self._new_full_sudoku
        valid = self._new_valid_sudoku
        valid[:] = full

        remaining_clues = 81

        while remaining_clues > max_pos_to_fill and used_count > 1:
            # Scan forward from a random position to find an untried cell
            i = rand.randrange(81)
            while True:
                i = i + 1 if i < 80 else 0
                if not used[i]:
                    break
            used[i] = True
            used_count -= 1

            if valid[i] == 0:
                # Already deleted (by symmetric partner)
                continue

            # For symmetric mode: skip if the symmetric partner is already gone
            # (unless this IS the center cell)
            is_center = (i // 9 == 4 and i % 9 == 4)
            symm = 9 * (8 - i // 9) + (8 - i % 9)

            if is_symmetric and not is_center and valid[symm] == 0:
                continue

            # Delete cell
            valid[i] = 0
            remaining_clues -= 1

            # Also delete symmetric partner (unless center cell)
            if is_symmetric and not is_center:
                valid[symm] = 0
                used[symm] = True
                used_count -= 1
                remaining_clues -= 1

            # Check uniqueness
            self.solve_values(valid)

            if self._solution_count > 1:
                # Restore — deletion would break uniqueness
                valid[i] = full[i]
                remaining_clues += 1
                if is_symmetric and not is_center:
                    valid[symm] = full[symm]
                    remaining_clues += 1

    def _generate_init_pos_pattern(self, pattern: list[bool]) -> bool:
        """Remove clues per a fixed pattern and check uniqueness.

        Mirrors ``SudokuGenerator.generateInitPos(boolean[])``.
        Returns ``True`` if the resulting puzzle has a unique solution.
        """
        valid = self._new_valid_sudoku
        valid[:] = self._new_full_sudoku

        for i in range(len(pattern)):
            if not pattern[i]:
                valid[i] = 0

        self.solve_values(valid)
        return self._solution_count <= 1

    # ------------------------------------------------------------------
    # Solve entry points
    # ------------------------------------------------------------------

    def _solve_grid(self, grid: Grid) -> None:
        """Set up stack from an existing Grid and solve."""
        self._stack[0].grid.set(grid)
        self._stack[0].index = 0
        self._stack[0].candidates = ()
        self._stack[0].cand_index = 0
        self._solve()

    def solve_string(self, sudoku_string: str) -> None:
        """Solve a puzzle given as an 81-character string."""
        if _gen_accel is not None:
            sol_count, sol = _gen_accel.solve_string(sudoku_string)
            self._solution_count = sol_count
            if sol_count >= 1:
                self._solution[:] = sol
            return

        s0 = self._stack[0]
        s0.grid.__init__()  # reset to empty
        s0.candidates = ()
        s0.cand_index = 0

        for i, ch in enumerate(sudoku_string[:LENGTH]):
            value = ord(ch) - ord("0")
            if 1 <= value <= 9:
                s0.grid.set_cell(i, value)
                if not _set_all_exposed_singles(s0.grid):
                    self._solution_count = 0
                    return

        self._solve()

    def solve_values(self, cell_values: list[int]) -> None:
        """Solve a puzzle given as an 81-element int list.

        Uses the fast bulk-set path (mirrors Java's ``solve(int[])``):
        set all values without propagation, rebuild internal data, then
        propagate singles once.
        """
        if _gen_accel is not None:
            sol_count, sol = _gen_accel.solve_values(cell_values)
            self._solution_count = sol_count
            if sol_count >= 1:
                self._solution[:] = sol
            return

        s0 = self._stack[0]
        s0.grid.__init__()  # reset to empty
        s0.candidates = ()
        s0.cand_index = 0

        # Bulk set: place values directly, strip candidates from buddies
        grid = s0.grid
        for i, value in enumerate(cell_values):
            if 1 <= value <= 9:
                grid.values[i] = value
                grid.candidates[i] = 0
                # Remove from buddy candidates
                buddies = BUDDIES[i]
                while buddies:
                    lsb = buddies & -buddies
                    j = lsb.bit_length() - 1
                    buddies ^= lsb
                    grid.candidates[j] &= ~DIGIT_MASKS[value]

        # Rebuild free counts, candidate_sets, and queues from scratch
        _rebuild_internal(grid)

        if not _set_all_exposed_singles(grid):
            self._solution_count = 0
            return

        self._solve()

    # ------------------------------------------------------------------
    # Core backtracking solver
    # ------------------------------------------------------------------

    def _solve(self) -> None:
        """Iterative backtracking solver.

        Mirrors ``SudokuGenerator.solve()`` (the private no-arg version).
        Uses the C accelerator if available, otherwise falls back to pure Python.
        """
        if _gen_accel is not None:
            self._solve_c()
        else:
            self._solve_py()

    def _solve_c(self) -> None:
        """C-accelerated solve path."""
        grid = self._stack[0].grid
        ns_q = list(grid.ns_queue)
        hs_q = list(grid.hs_queue)
        sol_count, sol = _gen_accel.solve(
            list(grid.values),
            list(grid.candidates),
            list(grid.candidate_sets),
            [list(row) for row in grid.free],
            ns_q,
            hs_q,
        )
        self._solution_count = sol_count
        if sol_count >= 1:
            self._solution[:] = sol

    def _solve_py(self) -> None:
        """Pure Python iterative backtracking solver.

        Mirrors ``SudokuGenerator.solve()`` (the private no-arg version).
        """
        self._solution_count = 0
        stack = self._stack

        # Propagate any queued singles from setup
        if not _set_all_exposed_singles(stack[0].grid):
            return

        if stack[0].grid.values.count(0) == 0:
            # Already solved
            self._solution[:] = stack[0].grid.values
            self._solution_count = 1
            return

        level = 0
        while True:
            unsolved = stack[level].grid.values.count(0)
            if unsolved == 0:
                # Found a solution
                self._solution_count += 1
                if self._solution_count == 1:
                    self._solution[:] = stack[level].grid.values
                elif self._solution_count > 1:
                    return  # more than one → done
            else:
                # Find the unsolved cell with fewest candidates (MRV)
                index = -1
                best_count = 9  # Java uses anzCand=9; cells with 9 cands are skipped
                grid = stack[level].grid
                for i in range(LENGTH):
                    cands = grid.candidates[i]
                    if cands != 0:
                        cnt = cands.bit_count()
                        if cnt < best_count:
                            best_count = cnt
                            index = i

                level += 1
                if index < 0:
                    # No candidates anywhere → invalid
                    self._solution_count = 0
                    return

                stack[level].index = index
                stack[level].candidates = _POSSIBLE_VALUES[
                    stack[level - 1].grid.candidates[index]
                ]
                stack[level].cand_index = 0

            # Try candidates at this level
            done = False
            while True:
                # Fall back through levels with no remaining candidates
                while stack[level].cand_index >= len(stack[level].candidates):
                    level -= 1
                    if level <= 0:
                        done = True
                        break
                if done:
                    break

                # Try next candidate
                next_cand = stack[level].candidates[stack[level].cand_index]
                stack[level].cand_index += 1

                # Copy parent state
                _copy_state(stack[level].grid, stack[level - 1].grid)

                if not _set_cell_valid(
                    stack[level].grid, stack[level].index, next_cand
                ):
                    continue  # invalid → try next candidate

                if _set_all_exposed_singles(stack[level].grid):
                    break  # valid move → advance to next level

            if done:
                break


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rebuild_internal(grid: Grid) -> None:
    """Rebuild free[], candidate_sets[], and queues from values/candidates.

    Called after bulk-setting values without full propagation (mirrors
    Java's ``Sudoku2.rebuildInternalData()``).
    """
    # Reset free counts
    for c in range(27):
        for d in range(10):
            grid.free[c][d] = 0

    # Reset candidate_sets
    for d in range(10):
        grid.candidate_sets[d] = 0

    # Clear queues
    grid.ns_queue.clear()
    grid.hs_queue.clear()

    for i in range(LENGTH):
        cands = grid.candidates[i]
        if cands == 0:
            continue  # solved cell
        for d in range(1, 10):
            if cands & DIGIT_MASKS[d]:
                grid.candidate_sets[d] |= 1 << i
                for c in CELL_CONSTRAINTS[i]:
                    grid.free[c][d] += 1

    # Enqueue naked singles and hidden singles
    for i in range(LENGTH):
        cands = grid.candidates[i]
        if cands != 0 and (cands & (cands - 1)) == 0:
            grid.ns_queue.append((i, cands.bit_length()))

    for c in range(27):
        for d in range(1, 10):
            if grid.free[c][d] == 1:
                rem = grid.candidate_sets[d] & ALL_UNIT_MASKS[c]
                if rem:
                    cell = (rem & -rem).bit_length() - 1
                    grid.hs_queue.append((cell, d))
