#!/usr/bin/env python3
"""Generate HTML parity report and SVG badge from pytest JUnit XML results.

Usage:
    python scripts/generate_parity_report.py \
        --results-dir parity-results/ \
        --output-dir site/

Expected layout of --results-dir:
    parity-results/
        parity-exemplars-1.0/
            parity-results.xml
        parity-qqwing_expert/
            parity-results.xml
        ...

Each subdirectory name is expected to start with "parity-"; the remainder
becomes the dataset name shown in the report.
"""

import argparse
import html
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def extract_failure_summary(message: str) -> str:
    """Extract the AssertionError body from a pytest failure message.

    Returns the lines between 'AssertionError:' and 'assert False', with the
    'E   ' pytest prefix stripped — i.e. just the human-readable assertion text.
    Falls back to the first 200 chars if the pattern isn't found.
    """
    lines = message.splitlines()
    summary = []
    in_error = False
    for line in lines:
        if "AssertionError:" in line:
            in_error = True
            rest = line[line.index("AssertionError:") + len("AssertionError:"):].strip()
            if rest and not rest.startswith("section:") and not rest.startswith("puzzle:"):
                summary.append(rest)
            continue
        if in_error:
            # Strip leading 'E' + whitespace (pytest prefix)
            content = line[1:].strip() if line.startswith("E") else line.strip()
            if content.startswith("assert False") or content.startswith("+  where"):
                break
            # Skip section/puzzle — already visible in the table
            if content.startswith("section:") or content.startswith("puzzle:"):
                continue
            summary.append(content)
    return "\n".join(summary) if summary else message[:200]


def parse_junit(xml_path: Path) -> tuple[dict, list[dict]]:
    """Return (stats, cases) from a junit XML file.

    stats: dict with tests/passed/failures/errors/skipped counts
    cases: list of dicts with keys: name, status, message
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    cases = []
    for tc in root.findall(".//testcase"):
            raw_name = tc.get("name", "")
            # Strip pytest wrapper: test_foo[...] -> ...
            if raw_name.endswith("]") and "[" in raw_name:
                name = raw_name[raw_name.index("[") + 1:-1]
            else:
                name = raw_name

            failure = tc.find("failure")
            skipped = tc.find("skipped")
            if failure is not None:
                status = "failed"
                message = (failure.text or failure.get("message", "")).strip()
                summary = extract_failure_summary(message)
            elif skipped is not None:
                status = "skipped"
                message = skipped.get("message", "").strip()
                summary = message
            else:
                status = "passed"
                message = ""
                summary = ""

            puzzle = ""
            score = ""
            level = ""
            for prop in tc.findall("properties/property"):
                pname = prop.get("name")
                if pname == "puzzle":
                    puzzle = prop.get("value", "")
                elif pname == "hodoku_score":
                    score = prop.get("value", "")
                elif pname == "hodoku_level_name":
                    level = prop.get("value", "")

            cases.append({"name": name, "status": status, "message": message, "summary": summary, "puzzle": puzzle, "score": score, "level": level})

    n_failures = sum(1 for c in cases if c["status"] == "failed")
    n_skipped = sum(1 for c in cases if c["status"] == "skipped")
    n_passed = sum(1 for c in cases if c["status"] == "passed")
    stats = {
        "tests": len(cases),
        "passed": n_passed,
        "failures": n_failures,
        "errors": 0,
        "skipped": n_skipped,
    }
    return stats, cases


def badge_color(pct: float) -> str:
    # Hex codes — anybadge accepts these reliably across versions
    # Only 100% gets green — any failure should stand out
    if pct >= 100:
        return "#4c1"      # bright green
    if pct >= 95:
        return "#dfb317"   # yellow
    if pct >= 90:
        return "#fe7d37"   # orange
    return "#e05d44"       # red


def generate_badge(label: str, value: str, color: str, path: Path) -> None:
    import anybadge

    b = anybadge.Badge(label=label, value=value, default_color=color)
    b.write_badge(str(path), overwrite=True)


_CLIPBOARD_SVG = (
    '<svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" '
    'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
    '<rect x="5" y="2" width="9" height="12" rx="1.5"/>'
    '<path d="M2 5H1.5A.5.5 0 0 0 1 5.5v9A.5.5 0 0 0 1.5 15H10a.5.5 0 0 0 .5-.5V14"/>'
    '<rect x="7.5" y="1" width="4" height="2.5" rx="0.75" fill="currentColor" stroke="none"/>'
    '</svg>'
)

# Shared CSS used by both index and dataset pages
_COMMON_CSS = """
    body { font-family: system-ui, sans-serif; max-width: 960px; margin: 2em auto; padding: 0 1em; color: #222; }
    h1 { font-size: 1.5em; margin-bottom: 0.3em; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 0.45em 0.9em; text-align: right; vertical-align: top; }
    th:first-child, td:first-child { text-align: left; }
    th:last-child, td:last-child { text-align: left; }
    th { background: #f4f4f4; }
    tr:nth-child(even) { background: #fafafa; }
    .footer { font-size: 0.8em; color: #666; margin-top: 1em; }
"""


def generate_index_html(rows: list, now: str) -> str:
    rows_html = ""
    for name, stats in rows:
        pct = (stats["passed"] / stats["tests"] * 100) if stats["tests"] > 0 else 0.0
        rows_html += (
            f"\n        <tr>"
            f"<td><a href='{html.escape(name)}.html'>{html.escape(name)}</a></td>"
            f"<td>{stats['tests']}</td>"
            f"<td>{stats['passed']}</td>"
            f"<td>{stats['failures'] + stats['errors']}</td>"
            f"<td>{stats['skipped']}</td>"
            f"<td><img src='badges/{html.escape(name)}.svg' alt='{pct:.1f}%'></td>"
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>hodoku-py parity report</title>
  <style>{_COMMON_CSS}
  </style>
</head>
<body>
  <h1>hodoku-py parity report</h1>
  <table>
    <thead>
      <tr>
        <th>Dataset</th>
        <th>Total</th>
        <th>Passed</th>
        <th>Failed</th>
        <th>Skipped</th>
        <th>Parity</th>
      </tr>
    </thead>
    <tbody>{rows_html}
    </tbody>
  </table>
  <p class="footer">Generated {now}</p>
</body>
</html>
"""


def generate_dataset_html(name: str, stats: dict, cases: list, now: str) -> str:
    pct = (stats["passed"] / stats["tests"] * 100) if stats["tests"] > 0 else 0.0

    rows_html = ""
    for case in cases:
        status = case["status"]
        badge_class = {"passed": "badge-pass", "failed": "badge-fail", "skipped": "badge-skip"}[status]
        badge_label = {"passed": "pass", "failed": "fail", "skipped": "skip"}[status]

        msg = case["message"]
        summary = case.get("summary", "") or msg
        msg_short = (summary[:200] + "…") if len(summary) > 200 else summary
        msg_attr = html.escape(msg, quote=True)
        msg_display = html.escape(msg_short)

        puzzle = case.get("puzzle", "")
        if puzzle:
            puzzle_widget = (
                f'<span class="puzzle-string" hidden>'
                f'<code>{html.escape(puzzle)}</code>'
                f' <button class="copy-btn" onclick="event.stopPropagation(); copyEl(this.previousElementSibling)" title="Copy to clipboard">{_CLIPBOARD_SVG}</button>'
                f'</span>'
            )
            td_name = f'<td class="name" onclick="toggleCell(this)" style="cursor:pointer"><button class="puzzle-toggle">+</button> {html.escape(case["name"])}{puzzle_widget}</td>'
        else:
            td_name = f'<td class="name">{html.escape(case["name"])}</td>'

        if msg:
            td_msg = (
                f'<td class="message" onclick="toggleMsg(this)" style="cursor:pointer">'
                f'<button class="msg-toggle">+</button>'
                f' <span class="msg-short">{msg_display}</span>'
                f'<div class="msg-full" hidden>'
                f'<pre>{html.escape(msg)}</pre>'
                f'<button class="copy-btn" onclick="event.stopPropagation(); copyEl(this.previousElementSibling)" title="Copy to clipboard">{_CLIPBOARD_SVG}</button>'
                f'</div>'
                f'</td>'
            )
        else:
            td_msg = '<td class="message"></td>'

        score = case.get("score", "")
        level_name = case.get("level", "")
        level_color = {
            "EASY":       "#2a7a2a",
            "MEDIUM":     "#80c040",
            "HARD":       "#c8a000",
            "UNFAIR":     "#e06820",
            "EXTREME":    "#d02020",
            "INCOMPLETE": "#888888",
        }.get(level_name, "#888888")
        td_level = f'<td class="level"><span style="color:{level_color};font-weight:500">{html.escape(level_name)}</span></td>' if level_name else '<td class="level"></td>'
        td_score = f'<td class="score">{html.escape(score)}</td>'

        row_num = len(rows_html.split('<tr')) - 1  # 1-based order index
        rows_html += (
            f'\n        <tr data-status="{status}" data-name="{html.escape(case["name"].lower(), quote=True)}" data-order="{row_num}">'
            f'<td class="order">{row_num}</td>'
            f'<td><span class="badge {badge_class}">{badge_label}</span></td>'
            f'{td_name}'
            f'{td_level}'
            f'{td_score}'
            f'{td_msg}'
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>hodoku-py parity — {html.escape(name)}</title>
  <style>{_COMMON_CSS}
    th[data-col] {{ cursor: pointer; user-select: none; }}
    th[data-col]:hover {{ background: #e8e8e8; }}
    th[data-col].sort-asc::after {{ content: " ▲"; font-size: 0.75em; }}
    th[data-col].sort-desc::after {{ content: " ▼"; font-size: 0.75em; }}
    th:nth-child(1), td:nth-child(1) {{ text-align: right; font-size: 0.8em; color: #aaa; width: 2.5em; }}
    th:nth-child(2), td:nth-child(2) {{ text-align: center; width: 4em; }}
    th:nth-child(3), td:nth-child(3) {{ text-align: left; font-family: monospace; font-size: 0.85em; }}
    th:nth-child(4), td:nth-child(4) {{ text-align: left; font-family: monospace; font-size: 0.85em; white-space: nowrap; }}
    th:nth-child(5), td:nth-child(5) {{ text-align: right; font-family: monospace; font-size: 0.85em; width: 4.5em; }}
    th:nth-child(6), td:nth-child(6) {{ text-align: left; font-size: 0.85em; color: #555; max-width: 400px; white-space: nowrap; }}
    .msg-short {{ display: inline-block; max-width: 360px; overflow: hidden; white-space: nowrap; vertical-align: middle; }}
    th:last-child, td:last-child {{ text-align: left; }}
    .controls {{ display: flex; gap: 0.6em; align-items: center; margin: 1em 0; flex-wrap: wrap; }}
    .controls input {{ padding: 0.35em 0.6em; border: 1px solid #ccc; border-radius: 4px; font-size: 0.9em; width: 280px; }}
    .toggle {{ padding: 0.3em 0.8em; border: 1px solid #ccc; border-radius: 4px; cursor: pointer; font-size: 0.85em; background: #f4f4f4; color: #444; }}
    .toggle.active {{ background: #e0e0e0; border-color: #999; font-weight: bold; color: #111; }}
    .toggle.active[data-status="passed"] {{ background: #d4edda; border-color: #4cae4c; color: #276228; }}
    .toggle.active[data-status="failed"] {{ background: #f8d7da; border-color: #c9302c; color: #842029; }}
    .toggle.active[data-status="skipped"] {{ background: #fff3cd; border-color: #d4a017; color: #664d03; }}
    .badge {{ display: inline-block; padding: 0.1em 0.5em; border-radius: 3px; font-size: 0.8em; font-weight: bold; }}
    .badge-pass {{ background: #d4edda; color: #276228; }}
    .badge-fail {{ background: #f8d7da; color: #842029; }}
    .badge-skip {{ background: #fff3cd; color: #664d03; }}
    .summary {{ color: #555; font-size: 0.95em; margin-bottom: 0.3em; }}
    #visible-count {{ font-size: 0.85em; color: #666; }}
    .puzzle-toggle, .msg-toggle {{ font-size: 0.75em; padding: 0 0.3em; margin-left: 0.4em; cursor: pointer; border: 1px solid #bbb; border-radius: 3px; background: #f4f4f4; vertical-align: middle; }}
    .puzzle-string:not([hidden]) {{ display: inline-flex; align-items: center; gap: 0.4em; margin-left: 0.4em; }}
    .puzzle-string code {{ font-size: 0.82em; color: #555; letter-spacing: 0.03em; }}
    .msg-full:not([hidden]) {{ display: block; margin-top: 0.4em; }}
    .msg-full pre {{ margin: 0 0 0.3em 0; font-size: 0.8em; white-space: pre-wrap; word-break: break-word; background: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 3px; padding: 0.4em 0.6em; color: #333; }}
    .copy-btn {{ font-size: 0.75em; padding: 0.1em 0.4em; cursor: pointer; border: 1px solid #bbb; border-radius: 3px; background: #f4f4f4; vertical-align: middle; }}
    #puzzle-tooltip {{ position: fixed; display: none; background: #fff; border: 1px solid #bbb; border-radius: 5px; padding: 6px; box-shadow: 0 3px 10px rgba(0,0,0,0.15); z-index: 1000; pointer-events: none; }}
    #puzzle-tooltip table {{ border-collapse: collapse; table-layout: fixed; width: 126px; }}
    #puzzle-tooltip td {{ width: 14px; height: 14px; padding: 0; text-align: center; vertical-align: middle; font-size: 11px; font-family: monospace; border: 1px solid #ddd; }}
    #puzzle-tooltip td.given {{ font-weight: bold; color: #111; }}
    #puzzle-tooltip td.box-right {{ border-right: 2px solid #555; }}
    #puzzle-tooltip td.box-bottom {{ border-bottom: 2px solid #555; }}
  </style>
</head>
<body>
  <div id="puzzle-tooltip"></div>
  <h1>hodoku-py parity — {html.escape(name)}</h1>
  <p class="summary">
    {stats['passed']} passed &nbsp;·&nbsp; {stats['failures']} failed &nbsp;·&nbsp;
    {stats['skipped']} skipped &nbsp;·&nbsp; {pct:.1f}%
    &nbsp;&nbsp;<img src="badges/{html.escape(name)}.svg" alt="{pct:.1f}%" style="vertical-align:middle">
  </p>
  <div class="controls">
    <input type="text" id="search" placeholder="Filter by name…" autocomplete="off">
    <button class="toggle active" data-status="all">All ({stats['tests']})</button>
    <button class="toggle" data-status="passed">Pass ({stats['passed']})</button>
    <button class="toggle" data-status="failed">Fail ({stats['failures']})</button>
    <button class="toggle" data-status="skipped">Skip ({stats['skipped']})</button>
    <span id="visible-count"></span>
  </div>
  <table>
    <thead>
      <tr>
        <th data-col="0">#</th>
        <th data-col="1">Status</th>
        <th data-col="2">Test</th>
        <th data-col="3">Level</th>
        <th data-col="4">Score</th>
        <th>Message</th>
      </tr>
    </thead>
    <tbody id="tbody">{rows_html}
    </tbody>
  </table>
  <p class="footer">Generated {now} &nbsp;·&nbsp; <a href="index.html">← back to index</a></p>
  <script>
    const rows = Array.from(document.querySelectorAll('#tbody tr'));
    const searchInput = document.getElementById('search');
    const toggles = document.querySelectorAll('.toggle');
    const countEl = document.getElementById('visible-count');
    let activeStatus = 'all';
    let searchTerm = '';
    let debounceTimer;

    function applyFilters() {{
      let visible = 0;
      for (const row of rows) {{
        const show = (activeStatus === 'all' || row.dataset.status === activeStatus) &&
                     row.dataset.name.includes(searchTerm);
        row.style.display = show ? '' : 'none';
        if (show) visible++;
      }}
      countEl.textContent = visible === rows.length ? '' : visible + ' shown';
    }}

    searchInput.addEventListener('input', () => {{
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {{
        searchTerm = searchInput.value.toLowerCase();
        applyFilters();
      }}, 150);
    }});

    for (const btn of toggles) {{
      btn.addEventListener('click', () => {{
        activeStatus = btn.dataset.status;
        for (const b of toggles) b.classList.remove('active');
        btn.classList.add('active');
        applyFilters();
      }});
    }}

    function toggleCell(td) {{
      const span = td.querySelector('.puzzle-string');
      const btn = td.querySelector('.puzzle-toggle');
      if (!span || !btn) return;
      span.hidden = !span.hidden;
      btn.textContent = span.hidden ? '+' : '-';
    }}

    function toggleMsg(td) {{
      const div = td.querySelector('.msg-full');
      const btn = td.querySelector('.msg-toggle');
      if (!div) return;
      div.hidden = !div.hidden;
      btn.textContent = div.hidden ? '+' : '-';
    }}

    function copyEl(el) {{
      const btn = el.nextElementSibling;
      const origHTML = btn.innerHTML;
      navigator.clipboard.writeText(el.textContent).then(() => {{
        btn.textContent = 'copied!';
        setTimeout(() => btn.innerHTML = origHTML, 1500);
      }});
    }}

    const tooltip = document.getElementById('puzzle-tooltip');

    function buildGrid(puzzle) {{
      let html = '<table>';
      for (let row = 0; row < 9; row++) {{
        html += '<tr>';
        for (let col = 0; col < 9; col++) {{
          const ch = puzzle[row * 9 + col];
          const given = ch !== '.' && ch !== '0';
          let cls = given ? 'given' : 'empty';
          if (col === 2 || col === 5) cls += ' box-right';
          if (row === 2 || row === 5) cls += ' box-bottom';
          html += `<td class="${{cls}}">${{given ? ch : ''}}</td>`;
        }}
        html += '</tr>';
      }}
      return html + '</table>';
    }}

    document.addEventListener('mouseover', e => {{
      const code = e.target.closest('.puzzle-string code');
      if (!code) return;
      const puzzle = code.textContent.trim();
      if (puzzle.length !== 81) return;
      tooltip.innerHTML = buildGrid(puzzle);
      tooltip.style.display = 'block';
    }});

    document.addEventListener('mouseout', e => {{
      if (e.target.closest('.puzzle-string code')) tooltip.style.display = 'none';
    }});

    // Sortable columns
    const tbody = document.getElementById('tbody');
    let sortCol = -1, sortAsc = true;
    const levelOrder = {{'EASY': 1, 'MEDIUM': 2, 'HARD': 3, 'UNFAIR': 4, 'EXTREME': 5, 'INCOMPLETE': 0}};

    function cellKey(row, col) {{
      const td = row.querySelectorAll('td')[col];
      if (!td) return '';
      if (col === 0) return parseInt(row.dataset.order) || 0;
      if (col === 1) return row.dataset.status || '';
      if (col === 3) return levelOrder[td.textContent.trim()] ?? 0;
      if (col === 4) return parseInt(td.textContent.trim()) || 0;
      return td.textContent.trim().toLowerCase();
    }}

    document.querySelectorAll('th[data-col]').forEach(th => {{
      th.addEventListener('click', () => {{
        const col = parseInt(th.dataset.col);
        if (sortCol === col) {{ sortAsc = !sortAsc; }}
        else {{ sortCol = col; sortAsc = true; }}
        document.querySelectorAll('th[data-col]').forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
        th.classList.add(sortAsc ? 'sort-asc' : 'sort-desc');
        const sorted = [...rows].sort((a, b) => {{
          const ka = cellKey(a, col), kb = cellKey(b, col);
          if (ka < kb) return sortAsc ? -1 : 1;
          if (ka > kb) return sortAsc ? 1 : -1;
          return 0;
        }});
        sorted.forEach(r => tbody.appendChild(r));
      }});
    }});

    document.addEventListener('mousemove', e => {{
      if (tooltip.style.display === 'none') return;
      const pad = 12;
      let x = e.clientX + pad;
      let y = e.clientY + pad;
      if (x + tooltip.offsetWidth > window.innerWidth) x = e.clientX - tooltip.offsetWidth - pad;
      if (y + tooltip.offsetHeight > window.innerHeight) y = e.clientY - tooltip.offsetHeight - pad;
      tooltip.style.left = x + 'px';
      tooltip.style.top = y + 'px';
    }});
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", required=True, help="Directory containing parity-* subdirs")
    parser.add_argument("--output-dir", required=True, help="Output directory for site files")
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "badges").mkdir(exist_ok=True)

    datasets = []
    for subdir in sorted(results_dir.iterdir()):
        if not subdir.is_dir():
            continue
        xml_path = subdir / "parity-results.xml"
        if not xml_path.exists():
            print(f"Warning: no parity-results.xml in {subdir}", file=sys.stderr)
            continue
        name = subdir.name
        if name.startswith("parity-"):
            name = name[len("parity-"):]
        stats, cases = parse_junit(xml_path)
        datasets.append((name, stats, cases))

    if not datasets:
        print("Error: no results found in", results_dir, file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for name, stats, cases in datasets:
        pct = (stats["passed"] / stats["tests"] * 100) if stats["tests"] > 0 else 0.0

        # Badge
        generate_badge(
            label=name,
            value=f"{pct:.1f}%",
            color=badge_color(pct),
            path=output_dir / "badges" / f"{name}.svg",
        )

        # Per-dataset page
        dataset_html = generate_dataset_html(name, stats, cases, now)
        (output_dir / f"{name}.html").write_text(dataset_html, encoding="utf-8")
        print(f"  {name}: {pct:.1f}%  ({stats['passed']}/{stats['tests']})  -> {name}.html")

    # Index
    index_rows = [(name, stats) for name, stats, _ in datasets]
    index_html = generate_index_html(index_rows, now)
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"Index:   {output_dir}/index.html")


if __name__ == "__main__":
    main()
