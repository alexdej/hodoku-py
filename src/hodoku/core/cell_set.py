"""81-cell bitset backed by a Python int."""

from __future__ import annotations

from typing import Iterator

_ALL_BITS = (1 << 81) - 1


class CellSet:
    """Bitset over the 81 cells of a sudoku grid (indices 0-80).

    Backed by a single Python int. Bit i corresponds to cell i.
    """

    __slots__ = ("_bits",)

    def __init__(self, bits: int = 0) -> None:
        self._bits = bits

    # --- mutation ---

    def add(self, index: int) -> None:
        self._bits |= 1 << index

    def remove(self, index: int) -> None:
        self._bits &= ~(1 << index)

    def clear(self) -> None:
        self._bits = 0

    def set_all(self) -> None:
        self._bits = _ALL_BITS

    def set(self, other: CellSet) -> None:
        self._bits = other._bits

    # --- set operations (in-place) ---

    def and_(self, other: CellSet) -> None:
        self._bits &= other._bits

    def or_(self, other: CellSet) -> None:
        self._bits |= other._bits

    def and_not(self, other: CellSet) -> None:
        self._bits &= ~other._bits

    # --- set operations (returning new CellSet) ---

    def intersection(self, other: CellSet) -> CellSet:
        return CellSet(self._bits & other._bits)

    def union(self, other: CellSet) -> CellSet:
        return CellSet(self._bits | other._bits)

    def difference(self, other: CellSet) -> CellSet:
        return CellSet(self._bits & ~other._bits)

    # --- query ---

    def contains(self, index: int) -> bool:
        return bool(self._bits >> index & 1)

    def is_empty(self) -> bool:
        return self._bits == 0

    def size(self) -> int:
        return self._bits.bit_count()

    def get(self, n: int) -> int:
        """Return the index of the nth set bit (0-based)."""
        bits = self._bits
        for _ in range(n):
            bits &= bits - 1  # clear lowest set bit
        return (bits & -bits).bit_length() - 1

    def first(self) -> int:
        """Return the lowest set index, or -1 if empty."""
        if self._bits == 0:
            return -1
        return (self._bits & -self._bits).bit_length() - 1

    def equals(self, other: CellSet) -> bool:
        return self._bits == other._bits

    # --- iteration ---

    def __iter__(self) -> Iterator[int]:
        bits = self._bits
        while bits:
            lsb = bits & -bits
            yield lsb.bit_length() - 1
            bits ^= lsb

    def __len__(self) -> int:
        return self._bits.bit_count()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CellSet):
            return self._bits == other._bits
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._bits)

    def __repr__(self) -> str:
        indices = list(self)
        return f"CellSet({indices})"

    def clone(self) -> CellSet:
        return CellSet(self._bits)
