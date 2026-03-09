# Exemplar Parity Failures

Baseline run: 570 passed, 99 failed (669 total)

## Failure Groups

### Group 1: Fish ordering (45 failures)
Sections: Franken Jellyfish (4), Finned Franken Swordfish (10), Finned Franken Jellyfish (11),
endo_fins (15), Finned Mutant Jellyfish (5)

**Symptom**: We find a different fish type/size than HoDoKu. E.g., we find FINNED_FRANKEN_X_WING
where HoDoKu finds FINNED_FRANKEN_SWORDFISH. Paths diverge from there.

**Root cause**: TBD — fish search ordering within Franken/Finned Franken solver.

### Group 2: ALS vs chains (27 failures)
Sections: ALS-XZ (11), ALS-XY-Wing (7), ALS-XY-Chain (9)

**Symptom**: We find GROUPED_DISCONTINUOUS_NICE_LOOP (index 5650) instead of ALS_XZ (index 5700).
Since GROUPED_DNL has lower priority index, our solver correctly tries it first. HoDoKu somehow
doesn't find the same chain at that point.

**Root cause**: TBD — possibly our chain solver finds spurious chains that HoDoKu doesn't,
or there's a difference in the chain search that makes us find different things.

### Group 3: Chain detail mismatches (22 failures)
Sections: CNL (4), set_value (10), delete_candidate (1), Type_1 (3), Grouped_Type_1 (2),
Grouped CNL (2)

**Symptom**: Same technique type but different eliminations or different chain found.
Some show AIC vs DNL type mismatch.

**Root cause**: TBD — chain elimination ordering or chain search differences.

### Group 4: Values ordering (4 failures)
Sections: Uniqueness Test Type 3 (2), Remote Pairs (2)

**Symptom**: Values tuple has wrong order: ours=(6,8) vs hodoku=(8,6).
Eliminations and technique type match perfectly.

**Root cause**: Values field ordering in step construction. Easy fix.

### Group 5: AR2 (1 failure)
Section: Avoidable Rectangle Type 2/p15

**Symptom**: We find DISCONTINUOUS_NICE_LOOP, HoDoKu finds AIC. Different elims entirely.

**Root cause**: Likely same as Group 3 — chain type/search difference.

## Priority

1. **Values ordering** (4 failures) — trivial fix
2. **Fish ordering** (45 failures) — investigate fish search order
3. **Chain/ALS divergence** (50 failures) — deeper investigation needed
