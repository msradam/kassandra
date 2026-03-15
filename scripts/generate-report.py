#!/usr/bin/env python3
"""Generate Kassandra markdown report from k6 JSON summary output.

Usage:
    python3 scripts/generate-report.py k6/kassandra/results/mr-37-spending.json

Reads k6 handleSummary JSON, writes a .md report alongside it, prints to stdout.
This runs AFTER k6 — the agent does NOT need to generate the report formatting.
"""

import json
import sys
from pathlib import Path


def format_report(data: dict) -> str:
    lines = []
    duration = data["state"]["testRunDurationMs"] / 1000
    metrics = data.get("metrics", {})
    http_reqs = metrics.get("http_reqs", {}).get("values", {}).get("count", 0)

    lines.append("## 🔮 Kassandra Performance Report\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Duration | {duration:.1f}s |")
    lines.append(f"| Total Requests | {http_reqs} |")
    lines.append("")

    # Threshold results
    threshold_rows = []
    for key, metric in metrics.items():
        thresholds = metric.get("thresholds")
        if not thresholds:
            continue
        for expr, result in thresholds.items():
            status = "✅ PASS" if result["ok"] else "❌ FAIL"
            threshold_rows.append(f"| {key} | `{expr}` | {status} |")

    if threshold_rows:
        lines.append("### Thresholds\n")
        lines.append("| Metric | Threshold | Status |")
        lines.append("|--------|-----------|--------|")
        lines.extend(threshold_rows)
        lines.append("")

    # Latency metrics table
    latency_rows = []
    for key, metric in metrics.items():
        if metric.get("type") != "trend" or metric.get("contains") != "time":
            continue
        v = metric["values"]
        latency_rows.append(
            f"| {key} | {v['avg']:.1f} | {v['med']:.1f} | {v.get('p(95)', 0):.1f} | {v.get('p(99)', 0):.1f} | {v['max']:.1f} |"
        )

    if latency_rows:
        lines.append("### Latency (ms)\n")
        lines.append("| Metric | Avg | Med | p95 | p99 | Max |")
        lines.append("|--------|-----|-----|-----|-----|-----|")
        lines.extend(latency_rows)
        lines.append("")

    # Mermaid latency chart for http_req_duration
    http_dur = metrics.get("http_req_duration")
    if http_dur and http_dur.get("type") == "trend":
        v = http_dur["values"]
        lines.append("```mermaid")
        lines.append("xychart-beta")
        lines.append('  title "HTTP Request Latency (ms)"')
        lines.append('  x-axis ["min", "avg", "med", "p90", "p95", "p99", "max"]')
        lines.append('  y-axis "Response Time (ms)"')
        bars = [v["min"], v["avg"], v["med"], v.get("p(90)", 0), v.get("p(95)", 0), v.get("p(99)", 0), v["max"]]
        lines.append(f"  bar [{', '.join(f'{b:.1f}' for b in bars)}]")
        lines.append("```\n")

    # Checks pass/fail pie chart
    checks = metrics.get("checks")
    if checks and checks.get("type") == "rate":
        passed = checks["values"].get("passes", 0)
        failed = checks["values"].get("fails", 0)
        lines.append("```mermaid")
        lines.append('pie title "Check Results"')
        lines.append(f'  "Passed ({passed})" : {passed}')
        lines.append(f'  "Failed ({failed})" : {failed}')
        lines.append("```\n")

    # Per-group breakdown (collapsible)
    root_group = data.get("root_group", {})
    groups = root_group.get("groups", [])
    if groups:
        lines.append("<details>")
        lines.append("<summary>Per-Endpoint Check Results</summary>\n")
        for group in groups:
            lines.append(f"**{group['name']}**")
            for check in group.get("checks", []):
                total = check["passes"] + check["fails"]
                pct = int((check["passes"] / total) * 100) if total > 0 else 0
                icon = "✅" if check["fails"] == 0 else "❌"
                lines.append(f"  {icon} {check['name']}: {pct}% ({check['passes']}/{total})")
            lines.append("")
        lines.append("</details>\n")

    lines.append("> 🔮 *Kassandra sees the performance problems you won't — until production.*")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: generate-report.py <k6-json-summary>", file=sys.stderr)
        sys.exit(1)

    json_path = Path(sys.argv[1])
    if not json_path.exists():
        print(f"Error: {json_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(json_path) as f:
        data = json.load(f)

    report = format_report(data)

    # Write .md alongside the .json
    md_path = json_path.with_suffix("").with_suffix("-report.md")
    md_path.write_text(report)

    # Also print to stdout
    print(report)


if __name__ == "__main__":
    main()
