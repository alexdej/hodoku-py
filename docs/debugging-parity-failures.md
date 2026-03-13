# Debugging Parity Test Failures (Python vs Java HoDoKu)

When parity tests fail (Python solver diverges from Java), follow this method:

## 1. Start with the earliest diverging step in the simplest failing puzzle

Run both solvers, print step-by-step output (type, elims, placements), find the first step that differs.

## 2. Classify the divergence

Is it a different technique type? Different eliminations? Different placement? Missing step? This narrows where to look.

## 3. Instrument both sides at the same logical point

Add print statements to the Java code (clone HoDoKu to `/workspace/HoDoKu-tmp`, build with `ant compile -Djavac.source=1.8 -Djavac.target=1.8 -Dbuild.dir=/tmp/hodoku-build`). Add matching prints to Python. Compare output side by side.

## 4. Trace backward from the divergence

If table entries differ, trace to table filling. If chains differ, trace to chain building. If eliminations differ, trace to the step-finding logic. Always go one level deeper until you find a single variable that differs.

## 5. The fix is almost always a line-by-line port discrepancy

Common categories:
- **Wrong object reference** (e.g., `saved_grid` vs `grid` — comments can mislead, trust the code)
- **Missing logic** (e.g., a parameter or early-termination check that wasn't ported)
- **Different algorithm** (e.g., "first" vs "middle" cell selection)
- **Missing filter** (e.g., discarding certain step types in a specific mode)

## 6. Use the gateway for quick Java comparison

```python
from tests.hodoku_gateway import HodokuGateway
gw = HodokuGateway()
result = gw.solve(puzzle)
# Step attributes: solution_type, technique, indices, values, eliminations
gw.shutdown()
```

## 7. Validate with reglib (fast, ~1min) before pushing

Only run top1465 in CI — it takes over an hour.

## Key insight

The codebase targets 100% fidelity with Java. Bugs are subtle porting errors, not algorithmic issues. Reading code alone won't find them — you need to see the actual values diverge.

## Examples from 2026-03-13 session

| Fix | Root cause | How found |
|-----|-----------|-----------|
| `grid.free` vs `saved_grid.free` | Java comment said "original candidates" but code uses current grid | Dumped ON table retIndices, saw different values, traced to `_set_cell_net` hidden single house selection |
| Missing chainSet early termination | Java's `buildChain` inner method has `tmpSetC` parameter Python didn't port | Dumped built chains, saw Python's net branches were longer than Java's |
| `_adjust_type` workaround | Python used `self._nets_mode or step.is_net()`, Java uses only `step.isNet()` | Compared step types, traced to `_adjust_type` and `_replace_or_copy_step` |
| Brute force middle cell | Java picks `unsolved.get(unsolved.size() / 2)`, Python picked first empty | Printed both solvers' step, both said BRUTE_FORCE but different cells |
