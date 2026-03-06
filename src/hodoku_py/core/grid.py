"""Grid — the central mutable state of a sudoku puzzle.

Mirrors Java's Sudoku2. Cells are indexed 0-80, row-major:
  row r, col c  →  index r*9 + c

Candidate masks: bit (d-1) set means digit d is still a candidate.
"""

from __future__ import annotations

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

# For each cell: (row_index, col_index, box_index)
def _build_constraints() -> tuple[tuple[int, int, int], ...]:
    result = []
    for i in range(81):
        r = i // 9
        c = i % 9
        b = (r // 3) * 3 + (c // 3)
        result.append((r, c, b))
    return tuple(result)

CONSTRAINTS: tuple[tuple[int, int, int], ...] = _build_constraints()

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

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def set_sudoku(self, puzzle: str) -> None:
        """Load an 81-character puzzle string ('.' or '0' for empty)."""
        digits = [c for c in puzzle if c.isdigit() or c == '.']
        if len(digits) != 81:
            raise ValueError(f"Expected 81 cells, got {len(digits)}: {puzzle!r}")
        self.__init__()
        for i, ch in enumerate(digits):
            if ch not in ('.', '0'):
                self.set_cell(i, int(ch))

    def get_sudoku_string(self) -> str:
        return "".join(str(v) if v else "0" for v in self.values)

    # ------------------------------------------------------------------
    # Cell mutation — keep values, candidates, and candidate_sets in sync
    # ------------------------------------------------------------------

    def set_cell(self, index: int, value: int) -> None:
        """Place a digit in a cell and propagate eliminations to buddies."""
        if self.values[index] == value:
            return
        self.values[index] = value
        # Remove all candidates from this cell
        old_mask = self.candidates[index]
        self.candidates[index] = 0
        for d in range(1, 10):
            if old_mask & DIGIT_MASKS[d]:
                self.candidate_sets[d] &= ~(1 << index)
        # Eliminate this digit from all buddies
        buddy_mask = BUDDIES[index]
        self.candidate_sets[value] &= ~buddy_mask
        buddies = buddy_mask
        while buddies:
            lsb = buddies & -buddies
            j = lsb.bit_length() - 1
            buddies ^= lsb
            if self.candidates[j] & DIGIT_MASKS[value]:
                self.candidates[j] &= ~DIGIT_MASKS[value]

    def del_candidate(self, index: int, digit: int) -> None:
        """Remove a candidate digit from a cell."""
        mask = DIGIT_MASKS[digit]
        if self.candidates[index] & mask:
            self.candidates[index] &= ~mask
            self.candidate_sets[digit] &= ~(1 << index)

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
        return g

    def set(self, other: Grid) -> None:
        """Copy another grid's state into self."""
        self.values = list(other.values)
        self.candidates = list(other.candidates)
        self.candidate_sets = list(other.candidate_sets)
        self.solution = list(other.solution)

    def __repr__(self) -> str:
        return f"Grid({self.get_sudoku_string()})"
