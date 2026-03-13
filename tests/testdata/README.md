# Test Data — Puzzle Files

Puzzle files for the [parity test suite](../parity/). Each file is plain text,
one puzzle per line (81 characters, digits and dots/zeros). Lines starting with
`#` are section labels.

## Files

| File | Puzzles | Description | Source | Status |
|------|--------:|-------------|--------|-------:|
| `exemplars-1.0.txt` | 669 | HoDoKu's built-in exemplar library, 57 technique sections | HoDoKu source | [![exemplars-1.0 parity](https://alexdej.github.io/hodoku-py/badges/exemplars-1.0.svg)](https://alexdej.github.io/hodoku-py/) |
| `top1465.txt` | 1,465 | Classic "top 1465" hard puzzle collection | [http://magictour.free.fr/top1465](http://magictour.free.fr/top1465) | [![top1465 parity](https://alexdej.github.io/hodoku-py/badges/top1465.svg)](https://alexdej.github.io/hodoku-py/) |
| `HardestDatabase110626.txt` | 375 | Hardest known puzzles (2011 compilation) | [Sudoku Players' Forum](http://forum.enjoysudoku.com/the-hardest-sudokus-new-thread-t6539.html) | |
| `qqwing_simple.sdm` | 1,000 | QQWing-generated, simple difficulty | [QQWing](https://qqwing.com/) | [![qqwing_simple parity](https://alexdej.github.io/hodoku-py/badges/qqwing_simple.svg)](https://alexdej.github.io/hodoku-py/) |
| `qqwing_easy.sdm` | 1,000 | QQWing-generated, easy difficulty | [QQWing](https://qqwing.com/) | [![qqwing_easy parity](https://alexdej.github.io/hodoku-py/badges/qqwing_easy.svg)](https://alexdej.github.io/hodoku-py/) |
| `qqwing_intermediate.sdm` | 1,000 | QQWing-generated, intermediate difficulty | [QQWing](https://qqwing.com/) | [![qqwing_intermediate parity](https://alexdej.github.io/hodoku-py/badges/qqwing_intermediate.svg)](https://alexdej.github.io/hodoku-py/) |
| `qqwing_expert.sdm` | 1,000 | QQWing-generated, expert difficulty | [QQWing](https://qqwing.com/) | [![qqwing_expert parity](https://alexdej.github.io/hodoku-py/badges/qqwing_expert.svg)](https://alexdej.github.io/hodoku-py/) |
| `sudoku17.sdm` | 49,151 | All known 17-clue puzzles | [Gordon Royle (Internet Wayback Machine)](https://web.archive.org/web/20120722180233/http://mapleta.maths.uwa.edu.au/~gordon/sudokumin.php) | |
| `sudocue_top10000.sdm` | 10,000 | SudoCue top 10,000 | [SudoCue](https://www.sudocue.net/) | |
| `sudocue_top50000.sdm` | 50,000 | SudoCue top 50,000 | [SudoCue](https://www.sudocue.net/) | |
| `sudocue_learningcurve.sdm` | 2,500 | SudoCue "learning curve" collection | [SudoCue](https://www.sudocue.net/) | |
| `sudocue_almostdn.sdm` | 400 | SudoCue "almost diabolically nasty" | [SudoCue](https://www.sudocue.net/) | |
| `sudocue_noponies.sdm` | 250 | SudoCue "no ponies" (very hard) | [SudoCue](https://www.sudocue.net/) | |
| `sudocue_snow2005.sdm` | 100 | SudoCue "snow 2005" collection | [SudoCue](https://www.sudocue.net/) | |
| `sudocue_superiors.sdm` | 160 | SudoCue "superiors" collection | [SudoCue](https://www.sudocue.net/) | |

## Adding a new puzzle file

1. Place the file in this directory (`.txt` or `.sdm` extension).
2. Run it with the parity suite:
   ```bash
   pytest tests/parity/ --puzzle-file <stem> -v
   ```
   where `<stem>` is the filename without extension.
3. For large files, use `--puzzle-count` to sample:
   ```bash
   pytest tests/parity/ --puzzle-file <stem> --puzzle-count 100 --puzzle-seed 42 -v
   ```
4. To include it in CI, add it to the matrix in `.github/workflows/parity.yml`.
