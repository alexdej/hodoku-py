from __future__ import annotations

from dataclasses import dataclass, field

from hodoku.core.types import SolutionType


@dataclass(frozen=True)
class Candidate:
    """A (cell, digit) pair — used in candidates_to_delete lists."""
    index: int  # 0-80
    value: int  # 1-9


@dataclass(frozen=True)
class Entity:
    """A house referenced in a hint description."""
    type: int    # Grid.ROW / Grid.COL / Grid.BOX / Grid.CELL
    number: int  # 1-based


@dataclass
class SolutionStep:
    """One logical step: the technique applied plus enough data to
    describe and apply it."""

    type: SolutionType

    # What to do to the grid
    indices: list[int] = field(default_factory=list)           # cells to set
    values: list[int] = field(default_factory=list)            # values for those cells
    candidates_to_delete: list[Candidate] = field(default_factory=list)

    # House context (for display / explanation)
    entity: int = 0
    entity_number: int = 0
    entity2: int = 0
    entity2_number: int = 0
    base_entities: list[Entity] = field(default_factory=list)
    cover_entities: list[Entity] = field(default_factory=list)

    # Fish-specific
    fins: list[Candidate] = field(default_factory=list)
    endo_fins: list[Candidate] = field(default_factory=list)
    is_siamese: bool = False

    # Chain / coloring
    chains: list[list[int]] = field(default_factory=list)      # each chain is list[int] (packed entries)
    color_candidates: dict[int, int] = field(default_factory=dict)

    # ALS-specific
    alses: list[tuple[int, int]] = field(default_factory=list)  # (CellSet bits, candidate mask)
    restricted_commons: list[tuple[int, int, int, int]] = field(default_factory=list)  # (als1, als2, cand1, cand2)

    # Progress scoring (filled in by SudokuSolver when requested)
    progress_score: int = -1
    progress_score_singles: int = -1
    progress_score_singles_only: int = -1

    def add_index(self, index: int) -> None:
        self.indices.append(index)

    def add_value(self, value: int) -> None:
        self.values.append(value)

    def add_candidate_to_delete(self, index: int, value: int) -> None:
        self.candidates_to_delete.append(Candidate(index, value))

    def add_als(self, indices: int, candidates: int) -> None:
        self.alses.append((indices, candidates))

    def reset(self) -> None:
        """Clear all fields for reuse (mirrors Java's globalStep.reset())."""
        self.indices.clear()
        self.values.clear()
        self.candidates_to_delete.clear()
        self.chains.clear()
        self.entity = 0
        self.entity_number = 0
        self.alses.clear()
        self.endo_fins.clear()
        self.fins.clear()
        self.color_candidates.clear()

    def is_net(self) -> bool:
        """True if any chain contains a negative entry (net branch marker)."""
        for chain in self.chains:
            for entry in chain:
                if entry < 0:
                    return True
        return False

    def get_chain_length(self) -> int:
        """Total length across all chains (sum of chain list lengths)."""
        total = 0
        for chain in self.chains:
            total += len(chain)
        return total

    def get_candidate_string(self) -> str:
        """Canonical string for dedup — sorted candidates_to_delete.

        Includes step type name so that different step types (e.g.
        FORCING_CHAIN_CONTRADICTION vs FORCING_CHAIN_VERITY) that
        happen to target the same candidates are kept in separate
        dedup buckets — matching Java's getCandidateString().

        IMPORTANT: sorts candidates_to_delete IN PLACE, matching Java's
        Collections.sort(candidatesToDelete).  Java's Candidate.compareTo
        sorts by value first, then by index.  The in-place sort is
        required so that getIndexSumme() in compareTo() sees the same
        ordering as Java.
        """
        self.candidates_to_delete.sort(key=lambda c: (c.value, c.index))
        parts = [(c.index, c.value) for c in self.candidates_to_delete]
        elim_str = ",".join(f"{i}:{v}" for i, v in parts)
        return f"{elim_str} ({self.type.name})"

    def get_single_candidate_string(self) -> str:
        """Canonical string for dedup — sorted indices/values (set-cell steps).

        Includes step type name for the same reason as
        get_candidate_string() — matching Java's getSingleCandidateString().
        """
        parts = sorted(zip(self.indices, self.values))
        cells_str = ",".join(f"{i}={v}" for i, v in parts)
        return f"{self.type.name}: {cells_str}"

    def __repr__(self) -> str:
        return f"SolutionStep({self.type.name}, indices={self.indices}, values={self.values})"
