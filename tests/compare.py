"""Shared helpers for comparing our solver output against HoDoKu's."""

from __future__ import annotations

from hodoku.core.types import SolutionType
from tests.hodoku_harness import HodokuResult


def solution_path(solver_result) -> list[tuple[SolutionType, tuple]]:
    """Convert our solve result to a comparable list of (type, outcome) tuples."""
    path = []
    for step in solver_result.steps:
        if step.candidates_to_delete:
            outcome = tuple(sorted((c.index, c.value) for c in step.candidates_to_delete))
        else:
            outcome = tuple(sorted(zip(step.indices, step.values)))
        path.append((step.type, outcome))
    return path


def hodoku_path(hodoku_result: HodokuResult) -> list[tuple[SolutionType | None, tuple]]:
    """Convert a HodokuResult to the same comparable form."""
    path = []
    for step in hodoku_result.steps:
        if step.eliminations:
            outcome = tuple(sorted(step.eliminations))
        else:
            outcome = tuple(sorted(zip(step.indices, step.values)))
        path.append((step.solution_type, outcome))
    return path


def first_divergence(ours: list[tuple], theirs: list[tuple]) -> str:
    """Return a human-readable description of where two paths first differ."""
    for i, (o, t) in enumerate(zip(ours, theirs)):
        if o != t:
            return (
                f"  first divergence at step {i + 1}:\n"
                f"    ours:   {o}\n"
                f"    hodoku: {t}"
            )
    n, m = len(ours), len(theirs)
    if n < m:
        return f"  our path ends early at step {n + 1}; hodoku next: {theirs[n]}"
    if n > m:
        return f"  hodoku path ends early at step {m + 1}; our next: {ours[m]}"
    return "  paths are identical (no divergence)"
