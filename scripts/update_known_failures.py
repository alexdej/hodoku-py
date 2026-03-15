#!/usr/bin/env python3
"""Run the exemplar regression suite and regenerate known_failures.txt.

Runs the full suite (or a specific section), extracts still-failing test IDs,
and overwrites tests/regression/known_failures.txt.  Prints a before/after
summary so you can see how many tests improved.

Usage:
    python scripts/update_known_failures.py
    python scripts/update_known_failures.py --section 0706
    python scripts/update_known_failures.py --count 100
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

KNOWN_FAILURES = Path(__file__).parent.parent / "tests" / "regression" / "known_failures.txt"


def run_suite(section: str | None, count: int) -> str:
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/regression/",
        f"--exemplar-count={count}",
        "-v", "--tb=no", "--no-header", "-q",
    ]
    if section:
        cmd += [f"--exemplar-section={section}"]

    print(f"Running: {' '.join(cmd[2:])}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout + result.stderr


def extract_xfail_ids(output: str) -> list[str]:
    ids = []
    for line in output.splitlines():
        m = re.search(r"test_matches_hodoku\[(\w+_\d+)\] XFAIL", line)
        if m:
            ids.append(m.group(1))
    return sorted(set(ids))


def extract_failed_ids(output: str) -> list[str]:
    ids = []
    for line in output.splitlines():
        m = re.search(r"FAILED.*test_matches_hodoku\[(\w+_\d+)\]", line)
        if m:
            ids.append(m.group(1))
    return sorted(set(ids))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--section", help="4-digit section code (e.g. 0706)")
    parser.add_argument("--count", type=int, default=670, help="Max exemplar count (default 670)")
    args = parser.parse_args()

    before = KNOWN_FAILURES.read_text().splitlines() if KNOWN_FAILURES.exists() else []
    before_set = set(before)

    output = run_suite(args.section, args.count)

    xfail_ids = extract_xfail_ids(output)
    failed_ids = extract_failed_ids(output)

    if failed_ids:
        print(f"\nWARNING: UNEXPECTED FAILURES ({len(failed_ids)}) - investigate before updating:")
        for fid in failed_ids:
            print(f"   {fid}")
        sys.exit(1)

    if args.section:
        # Partial run: merge new xfails for this section with existing others.
        section_prefix = args.section + "_"
        kept = [x for x in before if not x.startswith(section_prefix)]
        new_set = set(xfail_ids)
        merged = sorted(set(kept) | new_set)
    else:
        merged = xfail_ids

    KNOWN_FAILURES.write_text("\n".join(merged) + ("\n" if merged else ""))

    after_set = set(merged)
    fixed = sorted(before_set - after_set)
    added = sorted(after_set - before_set)

    print("\nknown_failures.txt updated.")
    print(f"  Before : {len(before_set):4d} known failures")
    print(f"  After  : {len(after_set):4d} known failures")
    if fixed:
        print(f"  Fixed  : {len(fixed):4d}  {fixed[:5]}{'...' if len(fixed) > 5 else ''}")
    if added:
        print(f"  Added  : {len(added):4d}  {added[:5]}{'...' if len(added) > 5 else ''}")
    if not fixed and not added:
        print("  No change.")

    # Print pytest summary line from output
    for line in output.splitlines():
        if re.search(r"\d+ passed", line):
            print(f"\n  {line.strip()}")
            break


if __name__ == "__main__":
    main()
