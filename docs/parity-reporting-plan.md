# Parity Reporting — Implementation Plan

## Goal

Replace the current "fail if not 100%" parity test behavior with a GitHub Pages
compatibility report. The parity tests are not regression tests (reglib covers
that) — they exist to publish a compatibility percentage.

## Design decisions made

- **No badge gists** — keep everything scoped to the repo
- **GitHub Pages** (`gh-pages` branch) hosts the generated site
- **Two-job GitHub Actions workflow**:
  - Job 1: run parity tests, output `--junit-xml=report.xml`, upload as artifact
  - Job 2: download artifact, generate HTML table + SVG badges, push to `gh-pages`
- Jobs are sequenced with `needs:` in the same workflow file
- The parity test job should **not fail the build** (`continue-on-error: true`) —
    job status = "did it complete", compatibility % = separate concern
- `peaceiris/actions-gh-pages` action handles the gh-pages push

## What to build

1. **GitHub Actions workflow** (`.github/workflows/parity-report.yml`)
   - Triggers: daily schedule + manual dispatch
   - Job 1 (`test`): runs pytest parity suite with `--junit-xml`, uploads XML artifact
   - Job 2 (`report`): downloads XML, runs site generator, pushes to gh-pages

2. **Site generator script** (`scripts/generate_parity_report.py`)
   - Reads junit XML (`report.xml`)
   - Generates:
     - `index.html` — table of datasets with pass/skip/fail counts and %
     - `badges/parity.svg` — overall compatibility badge
     - Per-dataset badges if desired
   - Use `anybadge` for SVG generation, plain Python for HTML

3. **README badge**
   - Embed `https://USERNAME.github.io/hodoku-py/badges/parity.svg`

## Parity test datasets

See `tests/parity/` and `tests/testdata/`. The parity suite takes `--puzzle-file`
pointing at an `.sdm` file. Likely datasets for the report:
- `top1465`
- `qqwing_expert`
- others in `tests/testdata/`

The workflow should run the suite once per dataset and produce one row in the
report table per dataset.

## Current parity test state

- ~649/669 passing (as of last known run)
- Tests use `tests/parity/test_parity.py` with `--puzzle-file` and `--puzzle-count`
- Requires Java (HoDoKu JAR) to run

## Notes

- The `gh-pages` branch is an orphan — no shared history with main
- `peaceiris/actions-gh-pages` handles creating/force-pushing it
- Python env in CI: plain `python` / `pytest`, no conda
- HoDoKu JAR is at `hodoku/hodoku.jar`
- Use jj (jujutsu) for commits, not git
- Project is low-maintenance — set it up once and leave it
