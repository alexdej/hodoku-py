#!/usr/bin/env python3
"""Analyze JUnit XML from parity test runs and bucket failures.

Usage:
    python scripts/analyze_parity_junit.py parity-results.xml
    python scripts/analyze_parity_junit.py parity-results.xml --save failures.txt
    python scripts/analyze_parity_junit.py parity-results.xml --puzzles-only
"""

from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass
class FailureInfo:
    puzzle_num: int
    puzzle: str
    our_steps: int
    hodoku_steps: int
    diverge_step: int
    diverge_kind: str  # "type", "placements", "elims"
    detail: str  # e.g. "FORCING_NET_VERITY vs FORCING_NET_CONTRADICTION"
    raw_message: str


def parse_failures(xml_path: str) -> tuple[int, int, list[FailureInfo]]:
    """Parse JUnit XML, return (total_tests, total_failures, failure_details)."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    total = 0
    failures: list[FailureInfo] = []

    for tc in root.iter("testcase"):
        total += 1
        fail_el = tc.find("failure")
        if fail_el is None:
            continue

        name = tc.get("name", "")
        msg = fail_el.get("message", "")

        m_pnum = re.search(r"::p(\d+)", name)
        pnum = int(m_pnum.group(1)) if m_pnum else -1

        m_puzzle = re.search(r"puzzle: ([0-9.]{81})", msg)
        puzzle = m_puzzle.group(1) if m_puzzle else ""

        m_steps = re.search(r"ours \((\d+) steps\) vs hodoku \((\d+) steps\)", msg)
        our_steps = int(m_steps.group(1)) if m_steps else 0
        hod_steps = int(m_steps.group(2)) if m_steps else 0

        m_div = re.search(r"first divergence at step (\d+)", msg)
        div_step = int(m_div.group(1)) if m_div else 0

        # Determine divergence kind
        m_kind = re.search(r"divergence at step \d+:\s*\n\s*(\w+):", msg)
        div_kind = m_kind.group(1) if m_kind else "unknown"

        # Extract detail
        detail = ""
        if div_kind == "type":
            m_types = re.search(r"type: ours=(\S+)\s+hodoku=(\S+)", msg)
            if m_types:
                ours_t = m_types.group(1).split(".")[-1]
                hod_t = m_types.group(2).split(".")[-1]
                detail = f"{ours_t} vs {hod_t}"
        elif div_kind == "placements":
            m_pl = re.search(r"placements: ours=(\S+)\s+hodoku=(\S+)", msg)
            if m_pl:
                detail = f"ours={m_pl.group(1)} hodoku={m_pl.group(2)}"
        elif div_kind == "elims":
            m_el = re.search(r"elims: ours=(\S+)\s+hodoku=(\S+)", msg)
            if m_el:
                detail = f"ours={m_el.group(1)} hodoku={m_el.group(2)}"

        failures.append(FailureInfo(
            puzzle_num=pnum,
            puzzle=puzzle,
            our_steps=our_steps,
            hodoku_steps=hod_steps,
            diverge_step=div_step,
            diverge_kind=div_kind,
            detail=detail,
            raw_message=msg,
        ))

    failures.sort(key=lambda f: f.puzzle_num)
    return total, len(failures), failures


def bucket_report(total: int, num_failures: int, failures: list[FailureInfo]) -> str:
    """Generate a human-readable bucketed report."""
    lines: list[str] = []
    pass_rate = 100 * (total - num_failures) / total if total else 0
    lines.append(f"Top1465 Parity Results: {total - num_failures}/{total} passed ({pass_rate:.1f}%)")
    lines.append(f"Failures: {num_failures}")
    lines.append("")

    # Bucket by divergence kind
    by_kind: dict[str, list[FailureInfo]] = {}
    for f in failures:
        by_kind.setdefault(f.diverge_kind, []).append(f)

    for kind in ["type", "placements", "elims", "unknown"]:
        group = by_kind.get(kind, [])
        if not group:
            continue
        lines.append(f"=== {kind.upper()} divergence: {len(group)} failures ===")

        if kind == "type":
            # Sub-bucket by type pair
            pairs: dict[str, list[FailureInfo]] = {}
            for f in group:
                pairs.setdefault(f.detail, []).append(f)
            for pair, items in sorted(pairs.items(), key=lambda x: -len(x[1])):
                lines.append(f"  {pair}: {len(items)} failures")
                pnums = [f"p{f.puzzle_num}" for f in items]
                lines.append(f"    {', '.join(pnums)}")
        else:
            for f in group:
                step_diff = f.our_steps - f.hodoku_steps
                lines.append(
                    f"  p{f.puzzle_num:<4d}  {f.our_steps:3d} vs {f.hodoku_steps:3d} steps "
                    f"(diff={step_diff:+3d})  diverge@step {f.diverge_step:2d}  {f.detail}"
                )
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze parity JUnit XML results")
    parser.add_argument("xml_file", help="Path to JUnit XML file")
    parser.add_argument("--save", metavar="FILE", help="Save report to file")
    parser.add_argument("--puzzles-only", action="store_true",
                        help="Print only the puzzle strings (one per line) for failed tests")
    args = parser.parse_args()

    total, num_failures, failures = parse_failures(args.xml_file)

    if args.puzzles_only:
        for f in failures:
            print(f.puzzle)
        return

    report = bucket_report(total, num_failures, failures)
    print(report)

    if args.save:
        with open(args.save, "w") as fh:
            fh.write(report + "\n")
        print(f"\nSaved to {args.save}")


if __name__ == "__main__":
    main()
