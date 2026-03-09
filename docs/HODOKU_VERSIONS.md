# HoDoKu Versions and the 2.3 Development Branch

## Background

HoDoKu was developed by "hobiwan" and released as open source. The final public
release was **2.2.0**, tagged in SVN on 2012-07-19 (r118). The author continued
working on a 2.3 release through mid-2013 but died before completing it. The
unfinished work is preserved in the SVN trunk.

**This project targets strict 2.2.0 fidelity.**

## SVN Repository

The SVN history is available at `../hodoku-svn` (relative to the project root).
The 2.2.0 source tarball is at `../HoDoKu` (the reference implementation we
port from and validate against).

```
r118   2012-07-19   2.2.0 release tag
r119   2012-07-29   post-release GUI changes
r120   2012-08-02   MainFrame
r121   2012-08-02   rename release-2.2.txt → release-2.3.txt (2.3 work begins)
r122   2012-08-03   TableEntry, TablingSolver
r123   2012-08-08   TableEntry, TablingSolver
r124   2012-08-13   TablingSolver, Chain, SudokuSetBase
                    ── one year gap ──
r125   2013-08-26   build files, GUI
r126   2013-08-26   MainFrame, SudokuPanel
r127   2013-08-26   TableEntry, TablingSolver
r128   2013-08-27   TablingSolver
r129   2013-08-28   TablingSolver
r130   2013-08-28   TablingSolver
r131   2013-08-28   GroupNode, TablingSolver, Sudoku2
r132   2013-08-28   Als, AlsSolver, SudokuStepFinder, FindAllSteps, RegressionTester
                    (rename getAllAlses → getAllAlsSteps; minor javadoc)
r133   2013-08-28   Als, TablingSolver
r134   2013-08-28   TablingSolver
r135   2013-08-28   SudokuStepFinder, TablingSolver
r136   2013-08-28   TablingSolver
r137   2013-08-28   TablingSolver
r138   2013-08-28   TablingSolver
r139   2013-08-28   reglib-1.3.txt → reglib-1.4.txt, TablingSolver, ConfigFindAllStepsPanel
r140   2013-08-29   RegressionTester  ← important: new ALS test harness flags
r141   2013-08-29   AlsSolver, RestrictedCommon, TablingSolver, Chain, SolutionStep, …
                    (debugging/serialization scaffolding; AlsComparator consistency check)
r142   2013-08-31   AlsSolver, TableEntry, TablingSolver, Main
r143   2013-08-31   AlsSolver, GroupNode, TableEntry, TablingSolver, Chain, SolutionStep
r144   2013-08-31   TableEntry, TablingSolver, Chain
r145   2013-09-02   TableEntry, TablingSolver
r146   2013-09-03   TablingSolver
r147   2013-09-06   TableEntry, TablingSolver, Chain, SolutionStep   ← last commit
```

The work was almost entirely in `TablingSolver` (grouped/forcing chains/nets).
**No algorithmic changes to the standalone ALS solver** (ALS-XZ, XY-Wing,
XY-Chain, Death Blossom) were made between 2.2.0 and the last commit.

### Commit-by-commit analysis

**r119-r121** (Jul-Aug 2012): GUI changes, rename release notes file to 2.3.

**r122-r124** (Aug 2012): All `TablingSolver`. Added `createAllNets()` pass
after `checkForcingChains()` — the start of the forcing nets feature. Added
`Comparable<SudokuSetBase>` to support `TreeMap<SudokuSet>` in the net code.

**r125-r131** (Aug 2013, after year gap): More `TablingSolver`/`GroupNode`
work. Build file updates. `Sudoku2.java` minor changes.

**r132** (Aug 2013): Rename `getAllAlses()` → `getAllAlsSteps()` in
`SudokuStepFinder` and callers. Javadoc on `Als.java`. `RegressionTester`
updated to call renamed method.

**r133** (Aug 2013): `Als.java` — pure javadoc. `TablingSolver` —
`fillTablesWithAls()` had a variable shadowing bug: outer loop variables `i`
and `j` were reused in inner contexts; renamed to `alsIndex`/`entryCand`. Also
a comment correction: "offEntry triggers the **off**Entry" → "triggers the
**on**Entry". This is in the forcing chains path only, not the standalone ALS
solver.

**r134**: `TablingSolver` only.

**r135** (Aug 2013): `SudokuStepFinder` — added `groupNodes` cache (same
pattern as existing ALS cache). Performance optimization, no algorithm change.
`TablingSolver` work.

**r136-r138**: `TablingSolver` only.

**r139** (Aug 2013): `reglib-1.3.txt` → `reglib-1.4.txt` (5 chain length
corrections in 0711-4 entries, see above). `TablingSolver`.

**r140** (Aug 2013): `RegressionTester` — added `setAllStepsAlsChainForwardOnly(false)`
and `setAllStepsAlsChainLength(6)` to the ALS reglib test harness (see above).
Otherwise cosmetic whitespace.

**r141** (Aug 2013): `RestrictedCommon`, `AlsInSolutionStep`, `Candidate`,
`SolutionStep` — all just added `Serializable`/`serialVersionUID` so he could
write ALS chain results to disk for offline analysis. `AlsSolver` — added
serialization debugging code (marked "TODO remove!") and a brute-force
`AlsComparator` consistency checker. Pure debugging infrastructure.

**r142-r147** (Aug-Sep 2013, last commits): `TableEntry` got a new `addEntry`
overload taking an `alsIndex` parameter and `containsEntry()` helper. More
`TablingSolver`/`Chain`/`SolutionStep` work on the forcing nets feature. Last
commit: 2013-09-06.

## reglib-1.3 vs reglib-1.4

The regression test library was updated at r139. Diffing the two files reveals
**exactly 5 changed lines**, all in `0711-4` (Grouped AIC variant 4) entries.
Only the `extra` field (chain length metadata) changed — puzzles, deleted
candidates, and eliminations are identical:

| entry | 1.3 length | 1.4 length |
|-------|-----------|-----------|
| 0711-4 cands=57 | 6 | 8 |
| 0711-4 cands=59 | 7 | 9 |
| 0711-4 cands=18 | 6 | 8 |
| 0711-4 cands=49 | 8 | 12 |
| 0711-4 cands=47 | 8 | 12 |

The chain lengths increased in every case, suggesting the 1.3 metadata was
understated and was corrected during 2.3 development. Since we don't validate
the `extra` field in our tests, this has no effect on pass/fail.

**We ship reglib-1.3.txt** (copied into `tests/reglib/`) as our test data,
matching 2.2.0 fidelity.

## Key 2.3 Change: ALS Reglib Test Harness (r140)

The most significant finding from the SVN history is r140's change to
`RegressionTester.java`. The 2.2.0 version sets these options before running
ALS reglib tests:

```java
// 2.2.0 (our target)
Options.getInstance().setOnlyOneAlsPerStep(false);
Options.getInstance().setAllowAlsOverlap(false);  // true for variant 2
```

The 2.3 version (r140) adds two more:

```java
// 2.3 additions
Options.getInstance().setAllStepsAlsChainForwardOnly(false);  // ← new
Options.getInstance().setAllStepsAlsChainLength(6);           // ← new
```

### What this means

**`allStepsAlsChainForwardOnly`**: In 2.2.0 this defaults to `true`, meaning
RC collection for ALS-XY-Chain only considers pairs `(als_i, als_j)` where
`j > i` (forward-only). Setting it to `false` makes RC collection bidirectional,
allowing longer and more varied chains.

**`allStepsAlsChainLength`**: Caps the maximum chain depth. Set to 6 in the
2.3 test harness.

The 1.3 reglib was generated and validated against 2.2.0 with `forwardOnly=true`
and the 2.2.0 default chain length. The 2.3 harness changes the search
parameters, which is why the 0711-4 chain lengths grew in 1.4 — the same
puzzles produce longer chains under the new settings.

### Implication for our failing ALS-XY-Chain tests

The 5 failing `0903` tests in our suite are likely puzzles where the expected
chain requires `forwardOnly=false` to find. They were **not** failures in the
original 1.3 test run against 2.2.0 — they only become failures if you apply
the 2.3 test harness settings to the 1.3 test data. Under strict 2.2.0
fidelity (our target), these are either legitimate bugs in our chain search or
edge cases that 2.2.0 also couldn't find.

To investigate: run the failing 0903 tests against the HoDoKu 2.2.0 JAR
directly to confirm whether 2.2.0 finds those chains or not.

## Targeting 2.3 in the Future

If a 2.3-compatible mode is ever desired, the changes needed are:

1. **ALS-XY-Chain**: implement `forwardOnly=false` mode in `_collect_rcs`
   (already has the `allow_overlap` param; add `forward_only=True` param)
2. **Test harness**: set `forward_only=False` and `chain_length=6` for
   `0901`/`0902`/`0903` reglib tests
3. **Replace reglib-1.3.txt with reglib-1.4.txt** in `tests/reglib/`
4. **TablingSolver**: the bulk of 2.3 work; r122-r147 are almost entirely
   `TablingSolver.java` changes for grouped/forcing chain improvements
