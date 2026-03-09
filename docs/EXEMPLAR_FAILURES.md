# Exemplar Parity Failures

Third run (after wiring TablingSolver + FC placement fix): **577 passed, 92 failed** (669 total)

## Changes since last run
- Wired TablingSolver into step_finder.py for Nice Loop/AIC/Forcing Chain types
  (was using chains.py DFS which found different/spurious chains)
- Fixed FORCING_CHAIN/NET steps not applying cell placements in solver.py
  (was causing infinite loop where same FC step was found repeatedly)
- Added grid fingerprint cache to avoid redundant table rebuilds
- Previous SPURIOUS_CHAIN failures (10) eliminated by routing NL through tabling
- Previous TIMEOUT failures (3) eliminated by FC placement fix
- Previous BRUTE_FORCE count reduced from 61 to ~1

## Failure Categories

### 1. DIFFERENT_CHAIN (~80 failures)
Same technique type found, but different eliminations — our tabling solver finds
a different (but equally valid) chain/loop at the same priority level.

Affects: endo_fins (14), Finned Franken Jellyfish (10), ALS-XZ (10), ALS-XY-Wing (9),
         ALS-XY-Chain (9), Finned Franken Swordfish (5), Finned Mutant Jellyfish (5),
         Franken Jellyfish (4), Type_1 (5), Type_2 (2), Grouped_Type_1 (2),
         set_value (5), AR2 (2), Grouped_Type_2 (1), GCNL (1), delete_candidate (1)

**Root cause**: Search ordering in TablingSolver table expansion and nice loop/AIC
detection. When multiple valid chains exist at the same priority level, our code
picks a different one than Java. This cascades — a different elimination changes
the grid state, which causes subsequent steps to diverge.

This is the dominant failure mode and the hardest to fix. Requires matching Java's
exact table expansion ordering, which depends on entry iteration order in TableEntry.

### 2. BRUTE_FORCE (1 failure)
ALS-XZ/p0: We fall through to brute force where HoDoKu finds FORCING_NET_CONTRADICTION.

**Root cause**: Forcing nets not implemented. Our `_get_forcing_nets()` falls back
to `_check_forcing_chains()`. Real forcing nets require net-mode table filling with
`chainsOnly=false` (recursive implication following in `fillTables`).

### 3. VALUES_ONLY (4 failures)
Same technique, same elims, but values field has different ordering.
- UT3/p9: Remote Pair values (6,8) vs (8,6)
- UT3/p25: different chain → different elims (reclassified as DIFFERENT_CHAIN)
- Remote Pairs/p13: values (4,5) vs (5,4)
- Remote Pairs/p15: values (2,3) vs (3,2)

**Root cause**: Remote Pair start candidate ordering. DFS explores chains in
different order than Java's stack-based search, picking a different start digit.

### 4. TYPE_MISMATCH (2 failures)
- set_value/p8: We find GROUPED_DNL, HoDoKu finds GROUPED_AIC
- endo_fins/p7: We find Grouped DNL, HoDoKu finds ALS-XY-Wing

**Root cause**: Chain type classification. GDNL and GAIC are closely related;
the classification depends on which chain is found first.

## Priority by ROI

1. **Chain ordering** (~80 failures) — dominant issue, very hard to fix
2. **Forcing nets** (1 failure) — implement `_check_forcing_nets()` properly
3. **Values ordering** (2 failures) — cosmetic fix for Remote Pair values
4. **Type mismatch** (2 failures) — chain classification
