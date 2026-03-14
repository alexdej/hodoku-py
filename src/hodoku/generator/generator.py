"""Backtracking solver for puzzle generation and solution counting.

Port of Java's ``SudokuGenerator`` — a bit-based backtracking solver that uses
the Grid's naked-single / hidden-single queues to propagate constraints during
search.  Used by the generator to:

* Check uniqueness (``valid_solution`` / ``get_number_of_solutions``).
* Produce the solution array stored on the Grid.
* (Later tasks) Generate full grids and derive puzzles by clue removal.

Reference: ``generator/SudokuGenerator.java`` lines 40–747.
"""

from __future__ import annotations

import collections

from hodoku.core.grid import (
    ALL_UNIT_MASKS,
    BUDDIES,
    CELL_CONSTRAINTS,
    DIGIT_MASKS,
    Grid,
    LENGTH,
)

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

    def __init__(self) -> None:
        self._stack: list[_StackEntry] = [_StackEntry() for _ in range(82)]
        self._solution: list[int] = [0] * LENGTH
        self._solution_count: int = 0

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
                best_count = 10
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
