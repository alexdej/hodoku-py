"""GeneratorPattern — a fixed given-pattern for puzzle generation.

Port of Java's ``GeneratorPattern`` class.  Indicates which cells must
contain givens when generating new puzzles.

Reference: ``generator/GeneratorPattern.java``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from hodoku.core.grid import LENGTH


@dataclass
class GeneratorPattern:
    """A pattern indicating which cells should contain givens.

    Parameters
    ----------
    name : str
        Human-readable name for the pattern.
    pattern : list[bool]
        81-element list; ``True`` means the cell must be a given.
    valid : bool
        Whether the pattern has been validated (can produce a unique puzzle).
    """

    name: str = ""
    pattern: list[bool] = field(default_factory=lambda: [False] * LENGTH)
    valid: bool = False

    def __post_init__(self) -> None:
        if len(self.pattern) != LENGTH:
            raise ValueError(
                f"pattern must have exactly {LENGTH} elements, "
                f"got {len(self.pattern)}"
            )

    @property
    def num_givens(self) -> int:
        """Return the number of cells marked as givens in the pattern."""
        return sum(self.pattern)

    def clone(self) -> GeneratorPattern:
        """Return a deep copy of this pattern."""
        return GeneratorPattern(
            name=self.name,
            pattern=list(self.pattern),
            valid=self.valid,
        )

    def __str__(self) -> str:
        return f"{self.name}: {self.pattern}"
