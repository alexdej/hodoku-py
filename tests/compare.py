"""Shared helpers for comparing our solver output against HoDoKu's."""

from __future__ import annotations

from dataclasses import dataclass

from hodoku.core.types import SolutionType
from tests.hodoku_harness import HodokuResult, HodokuStep


@dataclass(frozen=True)
class StepSummary:
    """Normalized step for comparison."""
    type: SolutionType | None
    eliminations: tuple[tuple[int, int], ...]   # sorted, deduped (cell, digit) pairs
    placements: tuple[tuple[int, int], ...]     # sorted (cell, digit) pairs
    indices: tuple[int, ...]                    # context cells (may be empty)
    values: tuple[int, ...]                     # context values (may be empty)


def _our_step(step) -> StepSummary:
    """Convert one of our SolutionStep objects to a StepSummary."""
    if step.candidates_to_delete:
        elims = tuple(sorted(set((c.index, c.value) for c in step.candidates_to_delete)))
        placements = ()
    else:
        elims = ()
        placements = tuple(sorted(zip(step.indices, step.values)))
    return StepSummary(
        type=step.type,
        eliminations=elims,
        placements=placements,
        indices=tuple(step.indices),
        values=tuple(step.values),
    )


def _hodoku_step(step: HodokuStep) -> StepSummary:
    """Convert a HodokuStep to a StepSummary."""
    if step.eliminations:
        elims = tuple(sorted(set(step.eliminations)))
        placements = ()
    else:
        elims = ()
        placements = tuple(sorted(zip(step.indices, step.values)))
    return StepSummary(
        type=step.solution_type,
        eliminations=elims,
        placements=placements,
        indices=tuple(step.indices),
        values=tuple(step.values),
    )


def our_steps(solver_result) -> list[StepSummary]:
    """Convert our solve result to a list of StepSummary."""
    return [_our_step(s) for s in solver_result.steps]


def hodoku_steps(hodoku_result: HodokuResult) -> list[StepSummary]:
    """Convert a HodokuResult to a list of StepSummary."""
    return [_hodoku_step(s) for s in hodoku_result.steps]


def steps_match(ours: StepSummary, theirs: StepSummary) -> bool:
    """Compare two steps using the asymmetric rule.

    Always compared: type, eliminations (deduped), placements.
    indices/values: skip if HoDoKu's side is empty (different representation).
    If our side is empty but HoDoKu's isn't, that's a mismatch (data we should have).
    """
    if ours.type != theirs.type:
        return False
    if ours.eliminations != theirs.eliminations:
        return False
    if ours.placements != theirs.placements:
        return False

    # Asymmetric detail comparison:
    # - HoDoKu empty → skip (they store it elsewhere, e.g. chains)
    # - HoDoKu non-empty → we must match
    if theirs.indices and ours.indices != theirs.indices:
        return False
    if theirs.values and ours.values != theirs.values:
        return False

    return True


def paths_match(ours: list[StepSummary], theirs: list[StepSummary]) -> bool:
    """Check if two solution paths match step-for-step."""
    if len(ours) != len(theirs):
        return False
    return all(steps_match(o, t) for o, t in zip(ours, theirs))


def first_divergence(ours: list[StepSummary], theirs: list[StepSummary]) -> str:
    """Return a human-readable description of where two paths first differ."""
    for i, (o, t) in enumerate(zip(ours, theirs)):
        if not steps_match(o, t):
            parts = [f"  first divergence at step {i + 1}:"]
            if o.type != t.type:
                parts.append(f"    type: ours={o.type} hodoku={t.type}")
            if o.eliminations != t.eliminations:
                parts.append(f"    elims: ours={o.eliminations[:5]} hodoku={t.eliminations[:5]}")
            if o.placements != t.placements:
                parts.append(f"    placements: ours={o.placements} hodoku={t.placements}")
            if t.indices and o.indices != t.indices:
                parts.append(f"    indices: ours={o.indices} hodoku={t.indices}")
            if t.values and o.values != t.values:
                parts.append(f"    values: ours={o.values} hodoku={t.values}")
            return "\n".join(parts)
    n, m = len(ours), len(theirs)
    if n < m:
        return f"  our path ends early at step {n + 1}; hodoku next: {theirs[n]}"
    if n > m:
        return f"  hodoku path ends early at step {m + 1}; our next: {ours[m]}"
    return "  paths are identical (no divergence)"


# ---------------------------------------------------------------------------
# Legacy helpers (used by tests/regression/)
# ---------------------------------------------------------------------------

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
