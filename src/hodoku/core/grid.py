"""Grid — the central mutable state of a sudoku puzzle.

Mirrors Java's Sudoku2. Cells are indexed 0-80, row-major:
  row r, col c  →  index r*9 + c

Candidate masks: bit (d-1) set means digit d is still a candidate.
"""

from __future__ import annotations

import collections

# ---------------------------------------------------------------------------
# Static lookup tables — computed once at module load, never mutated
# ---------------------------------------------------------------------------

LENGTH = 81
UNITS = 9

# row/col/box membership
LINES: tuple[tuple[int, ...], ...] = tuple(
    tuple(range(r * 9, r * 9 + 9)) for r in range(9)
)
COLS: tuple[tuple[int, ...], ...] = tuple(
    tuple(r * 9 + c for r in range(9)) for c in range(9)
)
BLOCKS: tuple[tuple[int, ...], ...] = tuple(
    tuple(
        (br * 3 + dr) * 9 + (bc * 3 + dc)
        for dr in range(3)
        for dc in range(3)
    )
    for br in range(3)
    for bc in range(3)
)
ALL_UNITS: tuple[tuple[int, ...], ...] = LINES + COLS + BLOCKS


# For each cell: (row_index, col_index, box_index) — all 0-based within their type
def _build_constraints() -> tuple[tuple[int, int, int], ...]:
    result = []
    for i in range(81):
        r = i // 9
        c = i % 9
        b = (r // 3) * 3 + (c // 3)
        result.append((r, c, b))
    return tuple(result)


CONSTRAINTS: tuple[tuple[int, int, int], ...] = _build_constraints()

# For each cell: indices into ALL_UNITS — (row_idx, col_idx+9, box_idx+18)
CELL_CONSTRAINTS: tuple[tuple[int, int, int], ...] = tuple(
    (r, c + 9, b + 18) for r, c, b in CONSTRAINTS
)


# Buddy sets: for each cell, the int bitmask of its 20 peers
def _build_buddies() -> tuple[int, ...]:
    buddies = []
    for i in range(81):
        r, c, b = CONSTRAINTS[i]
        mask = 0
        for j in LINES[r]:
            if j != i:
                mask |= 1 << j
        for j in COLS[c]:
            if j != i:
                mask |= 1 << j
        for j in BLOCKS[b]:
            if j != i:
                mask |= 1 << j
        buddies.append(mask)
    return tuple(buddies)


BUDDIES: tuple[int, ...] = _build_buddies()

# House bitmasks (for CellSet-style operations without CellSet objects)
LINE_MASKS: tuple[int, ...] = tuple(
    sum(1 << j for j in LINES[r]) for r in range(9)
)
COL_MASKS: tuple[int, ...] = tuple(
    sum(1 << j for j in COLS[c]) for c in range(9)
)
BLOCK_MASKS: tuple[int, ...] = tuple(
    sum(1 << j for j in BLOCKS[b]) for b in range(9)
)
ALL_UNIT_MASKS: tuple[int, ...] = LINE_MASKS + COL_MASKS + BLOCK_MASKS

# Digit masks for candidate shorts
DIGIT_MASKS: tuple[int, ...] = (0,) + tuple(1 << (d - 1) for d in range(1, 10))
ALL_DIGITS_MASK: int = 0x1FF  # bits 0-8 set


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------

class Grid:
    """Mutable sudoku grid."""

    __slots__ = (
        "values",
        "candidates",
        "candidate_sets",
        "solution",
        "free",
        "ns_queue",
        "hs_queue",
        "givens",
    )

    def __init__(self) -> None:
        # 0 = empty, 1-9 = placed digit
        self.values: list[int] = [0] * 81
        # per-cell candidate mask (9-bit int, bit d-1 = digit d present)
        self.candidates: list[int] = [ALL_DIGITS_MASK] * 81
        # per-digit bitmask of cells where that digit is still a candidate
        # index 0 unused; indices 1-9 are valid
        self.candidate_sets: list[int] = [0] * 10
        for d in range(1, 10):
            self.candidate_sets[d] = (1 << 81) - 1  # all cells initially
        # solution array — filled by generator after uniqueness check
        self.solution: list[int] = [0] * 81
        # free[constraint_index][digit] = count of unsolved cells in that
        # constraint still holding digit as a candidate.
        # 27 constraints (rows 0-8, cols 9-17, boxes 18-26), digits 0-9 (0 unused)
        self.free: list[list[int]] = [[0] * 10 for _ in range(27)]
        for c in range(27):
            for d in range(1, 10):
                self.free[c][d] = 9  # all 9 cells start with all candidates
        # Naked-single queue: (cell_index, digit) — cell has exactly 1 candidate left
        self.ns_queue: collections.deque[tuple[int, int]] = collections.deque()
        # Hidden-single queue: (constraint_index, digit) — constraint has exactly 1
        # cell left for digit
        self.hs_queue: collections.deque[tuple[int, int]] = collections.deque()
        # Bitmask of cells that are original givens (not placed during solving)
        self.givens: int = 0

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def set_sudoku(self, puzzle: str) -> None:
        """Load a puzzle string ('.' or '0' for empty).

        Digits prefixed with '+' are placed (solved) cells; digits without
        '+' are givens.  Both are set on the grid, but only non-'+' cells
        are recorded in the ``givens`` bitmask.
        """
        # Parse into (is_placed, char) pairs
        cells: list[tuple[bool, str]] = []
        i = 0
        while i < len(puzzle):
            ch = puzzle[i]
            if ch == '+':
                i += 1
                if i < len(puzzle) and (puzzle[i].isdigit() or puzzle[i] == '.'):
                    cells.append((True, puzzle[i]))
            elif ch.isdigit() or ch == '.':
                cells.append((False, ch))
            i += 1
        if len(cells) != 81:
            raise ValueError(f"Expected 81 cells, got {len(cells)}: {puzzle!r}")
        self.__init__()
        for idx, (is_placed, ch) in enumerate(cells):
            if ch not in ('.', '0'):
                self.set_cell(idx, int(ch))
                if not is_placed:
                    self.givens |= 1 << idx

    def is_fixed(self, index: int) -> bool:
        """True if the cell is an original given (not placed during solving)."""
        return bool(self.givens & (1 << index))

    def get_sudoku_string(self) -> str:
        return "".join(str(v) if v else "0" for v in self.values)

    # ------------------------------------------------------------------
    # Cell mutation — keep values, candidates, candidate_sets, free in sync
    # ------------------------------------------------------------------

    def _del_cand(self, index: int, digit: int) -> None:
        """Remove one candidate from a cell, update free[] and queues."""
        mask = DIGIT_MASKS[digit]
        if not (self.candidates[index] & mask):
            return
        self.candidates[index] &= ~mask
        self.candidate_sets[digit] &= ~(1 << index)
        for c in CELL_CONSTRAINTS[index]:
            self.free[c][digit] -= 1
            if self.free[c][digit] == 1:
                # Find the one remaining cell in this unit that still has digit.
                # candidate_sets[digit] is already updated, so bitwise-AND with
                # the unit mask gives exactly that cell.
                rem = self.candidate_sets[digit] & ALL_UNIT_MASKS[c]
                if rem:
                    cell = (rem & -rem).bit_length() - 1
                    self.hs_queue.append((cell, digit))
        remaining = self.candidates[index]
        if remaining != 0 and (remaining & (remaining - 1)) == 0:
            self.ns_queue.append((index, remaining.bit_length()))

    def set_cell(self, index: int, value: int) -> None:
        """Place a digit in a cell and propagate eliminations to buddies.

        Mirrors Sudoku2.setCell:
          1. Remove value from all buddy candidates (triggers HS/NS queue updates).
          2. Remove all remaining candidates from own cell, update free[].
        """
        if self.values[index] == value:
            return
        self.values[index] = value

        # Step 1: eliminate value from every buddy
        buddies = BUDDIES[index]
        while buddies:
            lsb = buddies & -buddies
            j = lsb.bit_length() - 1
            buddies ^= lsb
            self._del_cand(j, value)

        # Step 2: clear all remaining candidates from this cell, update free[]
        old_mask = self.candidates[index]
        self.candidates[index] = 0
        for d in range(1, 10):
            if old_mask & DIGIT_MASKS[d]:
                self.candidate_sets[d] &= ~(1 << index)
                for c in CELL_CONSTRAINTS[index]:
                    self.free[c][d] -= 1
                    if self.free[c][d] == 1 and d != value:
                        rem = self.candidate_sets[d] & ALL_UNIT_MASKS[c]
                        if rem:
                            cell = (rem & -rem).bit_length() - 1
                            self.hs_queue.append((cell, d))

    def del_candidate(self, index: int, digit: int) -> None:
        """Public API: remove a candidate digit from a cell."""
        self._del_cand(index, digit)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_value(self, index: int) -> int:
        return self.values[index]

    def get_candidates(self, index: int) -> list[int]:
        """Return list of candidate digits for a cell."""
        mask = self.candidates[index]
        result = []
        for d in range(1, 10):
            if mask & DIGIT_MASKS[d]:
                result.append(d)
        return result

    def is_solved(self) -> bool:
        return all(v != 0 for v in self.values)

    def unsolved_count(self) -> int:
        return self.values.count(0)

    def unsolved_candidates_count(self) -> int:
        return sum(c.bit_count() for c in self.candidates)

    def get_solution(self, index: int) -> int:
        return self.solution[index]

    def set_solution(self, solution: list[int]) -> None:
        self.solution = list(solution)

    def is_solution_set(self) -> bool:
        return any(v != 0 for v in self.solution)

    # ------------------------------------------------------------------
    # Cloning
    # ------------------------------------------------------------------

    def clone(self) -> Grid:
        g = Grid.__new__(Grid)
        g.values = list(self.values)
        g.candidates = list(self.candidates)
        g.candidate_sets = list(self.candidate_sets)
        g.solution = list(self.solution)
        g.free = [list(row) for row in self.free]
        g.ns_queue = collections.deque(self.ns_queue)
        g.hs_queue = collections.deque(self.hs_queue)
        return g

    def set(self, other: Grid) -> None:
        """Copy another grid's state into self."""
        self.values = list(other.values)
        self.candidates = list(other.candidates)
        self.candidate_sets = list(other.candidate_sets)
        self.solution = list(other.solution)
        self.free = [list(row) for row in other.free]
        self.ns_queue = collections.deque(other.ns_queue)
        self.hs_queue = collections.deque(other.hs_queue)

    def __repr__(self) -> str:
        return f"Grid({self.get_sudoku_string()})"
