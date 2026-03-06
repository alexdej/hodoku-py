from __future__ import annotations

from dataclasses import dataclass, field

from hodoku_py.core.types import SolutionType


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
    alses: list[tuple[int, int]] = field(default_factory=list) # (CellSet bits, candidate mask)
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

    def __repr__(self) -> str:
        return f"SolutionStep({self.type.name}, indices={self.indices}, values={self.values})"
