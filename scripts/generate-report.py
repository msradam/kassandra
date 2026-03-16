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


def _fmt(val: float, decimals: int = 1) -> str:
    """Format a number, handling None/missing."""
    if val is None:
        return "—"
    return f"{val:.{decimals}f}"


def _status_icon(ok: bool) -> str:
    return "✅" if ok else "❌"


def _extract_checks(group: dict, prefix: str = "") -> list[dict]:
    """Recursively extract checks from group hierarchy."""
    results = []
    checks = group.get("checks", [])
    if isinstance(checks, dict):
        checks = list(checks.values())
    for c in checks:
        total = c["passes"] + c["fails"]
        results.append({
            "group": prefix or "(root)",
            "name": c["name"],
            "passes": c["passes"],
            "fails": c["fails"],
            "total": total,
            "rate": c["passes"] / total if total > 0 else 0,
        })
    groups = group.get("groups", [])
    if isinstance(groups, dict):
        groups = list(groups.values())
    for g in groups:
        gname = g.get("name", "?")
        results.extend(_extract_checks(g, gname if not prefix else f"{prefix} > {gname}"))
    return results


def format_report(data: dict) -> str:
    lines = []
    duration = data["state"]["testRunDurationMs"] / 1000
    metrics = data.get("metrics", {})

    # ── Summary
    http_reqs = metrics.get("http_reqs", {}).get("values", {})
    http_failed = metrics.get("http_req_failed", {}).get("values", {})
    data_recv = metrics.get("data_received", {}).get("values", {})
    data_sent = metrics.get("data_sent", {}).get("values", {})
    dropped = metrics.get("dropped_iterations", {}).get("values", {})
    vus_max = metrics.get("vus_max", {}).get("values", {})

    total_reqs = http_reqs.get("count", 0)
    rps = http_reqs.get("rate", 0)
    fail_rate = http_failed.get("rate", 0)
    fail_count = http_failed.get("fails", 0)

    lines.append("## 🔮 Kassandra Performance Report\n")

    # Summary table
    lines.append("### Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| **Duration** | {duration:.1f}s |")
    lines.append(f"| **Total Requests** | {total_reqs:,} |")
    lines.append(f"| **Requests/sec** | {rps:.1f} |")
    lines.append(f"| **Failed Requests** | {fail_count} ({fail_rate:.1%}) |")
    if vus_max.get("value"):
        lines.append(f"| **Max VUs** | {int(vus_max['value'])} |")
    if dropped.get("count", 0) > 0:
        lines.append(f"| **Dropped Iterations** | {int(dropped['count'])} ⚠️ |")
    recv_kb = data_recv.get("count", 0) / 1024
    sent_kb = data_sent.get("count", 0) / 1024
    lines.append(f"| **Data Transferred** | ↓ {recv_kb:.0f} KB / ↑ {sent_kb:.0f} KB |")
    lines.append("")

    # ── Threshold results
    threshold_rows = []
    all_pass = True
    for key, metric in sorted(metrics.items()):
        thresholds = metric.get("thresholds")
        if not thresholds:
            continue
        for expr, result in thresholds.items():
            ok = result["ok"]
            if not ok:
                all_pass = False
            # Clean up metric name for display
            display_name = key
            if "{" in key:
                base, tag = key.split("{", 1)
                tag = tag.rstrip("}")
                display_name = f"{base} `{tag}`"
            threshold_rows.append(f"| {display_name} | `{expr}` | {_status_icon(ok)} |")

    if threshold_rows:
        status_line = "✅ **All thresholds passed**" if all_pass else "❌ **Some thresholds breached**"
        lines.append(f"### Thresholds — {status_line}\n")
        lines.append("| Metric | Threshold | Result |")
        lines.append("|--------|-----------|--------|")
        lines.extend(threshold_rows)
        lines.append("")

    # ── Per-endpoint latency table
    endpoint_metrics = {}
    global_duration = None
    for key, metric in metrics.items():
        if metric.get("type") != "trend" or metric.get("contains") != "time":
            continue
        if key == "http_req_duration":
            global_duration = metric["values"]
        elif key.startswith("http_req_duration{endpoint:"):
            ep_name = key.split("endpoint:", 1)[1].rstrip("}")
            endpoint_metrics[ep_name] = metric["values"]

    lines.append("### Latency Distribution\n")
    lines.append("| Endpoint | Avg | Med | p90 | p95 | p99 | Max |")
    lines.append("|----------|-----|-----|-----|-----|-----|-----|")
    if global_duration:
        v = global_duration
        lines.append(
            f"| **All (global)** | {_fmt(v['avg'])} | {_fmt(v['med'])} | "
            f"{_fmt(v.get('p(90)'))} | {_fmt(v.get('p(95)'))} | "
            f"{_fmt(v.get('p(99)'))} | {_fmt(v['max'])} |"
        )
    for ep_name, v in sorted(endpoint_metrics.items()):
        lines.append(
            f"| {ep_name} | {_fmt(v['avg'])} | {_fmt(v['med'])} | "
            f"{_fmt(v.get('p(90)'))} | {_fmt(v.get('p(95)'))} | "
            f"{_fmt(v.get('p(99)'))} | {_fmt(v['max'])} |"
        )
    lines.append("")

    # ── Timing breakdown (where time is spent)
    timing_keys = [
        ("http_req_blocked", "Blocked"),
        ("http_req_connecting", "Connecting"),
        ("http_req_tls_handshaking", "TLS"),
        ("http_req_sending", "Sending"),
        ("http_req_waiting", "Waiting (TTFB)"),
        ("http_req_receiving", "Receiving"),
    ]
    timing_rows = []
    for metric_key, label in timing_keys:
        m = metrics.get(metric_key)
        if m and m.get("type") == "trend":
            v = m["values"]
            avg = v.get("avg", 0)
            if avg > 0.01:  # only show non-trivial phases
                timing_rows.append(f"| {label} | {_fmt(avg)} | {_fmt(v.get('p(95)'))} | {_fmt(v['max'])} |")

    if timing_rows:
        lines.append("### Timing Breakdown\n")
        lines.append("| Phase | Avg (ms) | p95 (ms) | Max (ms) |")
        lines.append("|-------|----------|----------|----------|")
        lines.extend(timing_rows)
        lines.append("")

    # ── Custom business metrics
    builtin_prefixes = (
        "http_req_", "http_reqs", "vus", "iteration", "data_",
        "checks", "group_duration", "dropped_iterations",
    )
    custom_rows = []
    for key, metric in sorted(metrics.items()):
        if any(key.startswith(p) or key == p for p in builtin_prefixes):
            continue
        if "{" in key:
            continue
        mtype = metric.get("type")
        v = metric.get("values", {})
        if mtype == "trend":
            custom_rows.append(f"| {key} | Trend | avg={_fmt(v.get('avg'))} med={_fmt(v.get('med'))} p95={_fmt(v.get('p(95)'))} max={_fmt(v.get('max'))} |")
        elif mtype == "rate":
            custom_rows.append(f"| {key} | Rate | {v.get('rate', 0):.1%} ({v.get('passes', 0)}/{v.get('passes', 0) + v.get('fails', 0)}) |")
        elif mtype == "counter":
            custom_rows.append(f"| {key} | Counter | {v.get('count', 0):,.0f} |")
        elif mtype == "gauge":
            custom_rows.append(f"| {key} | Gauge | {_fmt(v.get('value'))} |")

    if custom_rows:
        lines.append("### Custom Metrics\n")
        lines.append("| Metric | Type | Value |")
        lines.append("|--------|------|-------|")
        lines.extend(custom_rows)
        lines.append("")

    # ── Mermaid: per-endpoint latency comparison chart
    if endpoint_metrics:
        lines.append("### Latency by Endpoint\n")
        lines.append("```mermaid")
        lines.append("xychart-beta")
        lines.append('  title "p95 Latency by Endpoint (ms)"')
        ep_names = sorted(endpoint_metrics.keys())
        labels = ", ".join(f'"{n}"' for n in ep_names)
        p95_vals = ", ".join(_fmt(endpoint_metrics[n].get("p(95)", 0)) for n in ep_names)
        lines.append(f"  x-axis [{labels}]")
        lines.append('  y-axis "Response Time (ms)"')
        lines.append(f"  bar [{p95_vals}]")
        lines.append("```\n")
    elif global_duration:
        # Fallback: show global latency distribution
        v = global_duration
        lines.append("### Latency Distribution\n")
        lines.append("```mermaid")
        lines.append("xychart-beta")
        lines.append('  title "HTTP Request Latency (ms)"')
        lines.append('  x-axis ["min", "avg", "med", "p90", "p95", "p99", "max"]')
        lines.append('  y-axis "Response Time (ms)"')
        bars = [v["min"], v["avg"], v["med"], v.get("p(90)", 0), v.get("p(95)", 0), v.get("p(99)", 0), v["max"]]
        lines.append(f"  bar [{', '.join(_fmt(b) for b in bars)}]")
        lines.append("```\n")

    # ── Mermaid: check results pie chart
    checks_metric = metrics.get("checks")
    if checks_metric and checks_metric.get("type") == "rate":
        passed = checks_metric["values"].get("passes", 0)
        failed = checks_metric["values"].get("fails", 0)
        if passed + failed > 0:
            lines.append("### Check Results\n")
            lines.append("```mermaid")
            lines.append('pie title "Validation Checks"')
            lines.append(f'  "Passed ({passed})" : {passed}')
            if failed > 0:
                lines.append(f'  "Failed ({failed})" : {failed}')
            lines.append("```\n")

    # ── Per-group check breakdown (collapsible)
    all_checks = _extract_checks(data.get("root_group", {}))
    if all_checks:
        # Group checks by group name
        by_group: dict[str, list] = {}
        for c in all_checks:
            by_group.setdefault(c["group"], []).append(c)

        lines.append("<details>")
        lines.append("<summary><strong>Per-Endpoint Validation Details</strong></summary>\n")
        for group_name, checks in by_group.items():
            all_ok = all(c["fails"] == 0 for c in checks)
            lines.append(f"**{_status_icon(all_ok)} {group_name}**\n")
            lines.append("| Check | Result | Pass Rate |")
            lines.append("|-------|--------|-----------|")
            for c in checks:
                icon = _status_icon(c["fails"] == 0)
                lines.append(f"| {c['name']} | {icon} {c['passes']}/{c['total']} | {c['rate']:.0%} |")
            lines.append("")
        lines.append("</details>\n")

    # ── Scenarios info (if present)
    options = data.get("options", {})
    scenarios = options.get("scenarios", {})
    if scenarios:
        lines.append("<details>")
        lines.append("<summary><strong>Scenario Configuration</strong></summary>\n")
        lines.append("| Scenario | Executor | Rate | Duration |")
        lines.append("|----------|----------|------|----------|")
        for name, cfg in scenarios.items():
            executor = cfg.get("executor", "?")
            rate = cfg.get("rate", cfg.get("startRate", "—"))
            dur = cfg.get("duration", "—")
            if "stages" in cfg:
                stages = cfg["stages"]
                dur = f"{len(stages)} stages"
            lines.append(f"| {name} | {executor} | {rate}/s | {dur} |")
        lines.append("\n</details>\n")

    lines.append("---")
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
    md_path = json_path.parent / (json_path.stem + "-report.md")
    md_path.write_text(report)

    # Also print to stdout
    print(report)


if __name__ == "__main__":
    main()
