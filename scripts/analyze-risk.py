#!/usr/bin/env python3
"""Pre-test risk analysis — scan diffs for performance anti-patterns.

Usage:
    python3 scripts/analyze-risk.py --diff-stdin < diff.patch
    echo "diff content" | python3 scripts/analyze-risk.py --diff-stdin

Outputs a markdown section with flagged risks, suitable for embedding in
the Kassandra report or posting as a separate MR comment.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass


@dataclass
class Risk:
    severity: str  # "high", "medium", "low"
    category: str
    description: str
    line_hint: str  # approximate line or context from the diff
    suggestion: str


# ── Pattern definitions ──
# Each pattern: (compiled regex, category, severity, description, suggestion)
# These run against added lines (lines starting with +) in the diff.

PATTERNS = [
    # N+1 query patterns
    (
        re.compile(r'for\s+.+\s+in\s+.+:\s*$', re.MULTILINE),
        "n_plus_one",
        None,  # severity set dynamically based on context
        "Loop detected — check for N+1 queries if DB calls are inside",
        "Batch queries or use JOINs instead of per-iteration lookups",
    ),
    # Unbounded SELECT (no LIMIT)
    (
        re.compile(r'SELECT\s+.*\s+FROM\s+(?!.*LIMIT)', re.IGNORECASE),
        "unbounded_query",
        "medium",
        "SELECT without LIMIT — may return unbounded result sets under load",
        "Add LIMIT/OFFSET or pagination to prevent memory exhaustion",
    ),
    # Missing pagination in list endpoints
    (
        re.compile(r'\.fetchall\(\)', re.IGNORECASE),
        "unbounded_fetch",
        "medium",
        "fetchall() loads all rows into memory at once",
        "Use pagination with LIMIT/OFFSET or cursor-based fetching",
    ),
    # Synchronous sleep in request handlers
    (
        re.compile(r'time\.sleep\(|import\s+time'),
        "sync_sleep",
        "high",
        "Synchronous sleep blocks the event loop / worker thread",
        "Use async sleep (asyncio.sleep) or remove the sleep entirely",
    ),
    # No connection pooling (creating connections per-request)
    (
        re.compile(r'(sqlite3\.connect|psycopg2\.connect|mysql\.connector\.connect|pymongo\.MongoClient)\('),
        "no_connection_pool",
        "medium",
        "Database connection created per-request — no connection pooling",
        "Use a connection pool (SQLAlchemy pool, psycopg2.pool, etc.)",
    ),
    # String formatting in SQL (injection + no prepared statement caching)
    (
        re.compile(r'(f"[^"]*(?:SELECT|INSERT|UPDATE|DELETE)|f\'[^\']*(?:SELECT|INSERT|UPDATE|DELETE)|\.format\(.*(?:SELECT|INSERT|UPDATE|DELETE))', re.IGNORECASE),
        "sql_string_format",
        "high",
        "SQL query built with string formatting — risk of injection and no query plan caching",
        "Use parameterized queries (?, %s) for safety and performance",
    ),
    # Large payload without streaming
    (
        re.compile(r'json\.dumps\(.*\)|jsonify\(.*\)|\.json\(\)'),
        "large_payload",
        "low",
        "JSON serialization detected — verify response size is bounded",
        "Consider pagination, field selection, or streaming for large payloads",
    ),
    # Missing index hints (new column in WHERE/ORDER BY)
    (
        re.compile(r'(WHERE|ORDER\s+BY|GROUP\s+BY)\s+\w+\.\w+', re.IGNORECASE),
        "missing_index",
        "low",
        "Query filter/sort on column — ensure index exists",
        "Add database index for columns used in WHERE/ORDER BY/GROUP BY",
    ),
    # Regex in hot path
    (
        re.compile(r're\.(compile|match|search|findall|sub)\('),
        "regex_hot_path",
        "low",
        "Regex operation — may be expensive if called per-request at high load",
        "Pre-compile regex patterns at module level, not per-request",
    ),
    # Nested loops (O(n²))
    (
        re.compile(r'for\s+\w+\s+in\s+.*:\s*\n\s+for\s+\w+\s+in', re.MULTILINE),
        "nested_loop",
        "medium",
        "Nested loop detected — O(n²) complexity may degrade under load",
        "Consider using dicts/sets for O(1) lookups or batch operations",
    ),
    # File I/O in request handler
    (
        re.compile(r'(open\(|Path\(.*\)\.(read|write)|\.read_text\(\)|\.write_text\(\))'),
        "file_io",
        "medium",
        "File I/O in request path — disk operations are slow under concurrency",
        "Cache file contents or move to async I/O",
    ),
    # External HTTP calls (latency amplification)
    (
        re.compile(r'(requests\.(get|post|put|delete)|httpx\.(get|post|put|delete)|urllib\.request\.urlopen)'),
        "external_call",
        "high",
        "Synchronous external HTTP call — latency is amplified under load",
        "Use async HTTP client, add timeouts, implement circuit breakers",
    ),
]

# Patterns that escalate N+1 detection when found near a loop
DB_CALL_PATTERNS = re.compile(
    r'(\.execute\(|\.query\(|\.find\(|\.findOne\(|\.findAll\(|'
    r'\.get\(|\.filter\(|\.select\(|Session\.)',
    re.IGNORECASE,
)


def analyze_diff(diff_text: str) -> list[Risk]:
    """Scan a unified diff for performance anti-patterns."""
    risks: list[Risk] = []
    seen_categories: set[str] = set()

    # Extract only added lines (with context for loop detection)
    added_lines = []
    for line in diff_text.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            added_lines.append(line[1:])  # Strip the + prefix

    added_text = "\n".join(added_lines)

    for pattern, category, severity, description, suggestion in PATTERNS:
        matches = list(pattern.finditer(added_text))
        if not matches:
            continue

        # Deduplicate: only report each category once
        if category in seen_categories:
            continue
        seen_categories.add(category)

        # Special handling for N+1: check if DB calls are near loops
        if category == "n_plus_one":
            # Look for DB calls within 5 lines after each loop
            has_db_in_loop = False
            for match in matches:
                start = match.end()
                # Get next 5 lines after the loop
                context_after = added_text[start:start + 500]
                next_lines = context_after.split("\n")[:5]
                for nl in next_lines:
                    if DB_CALL_PATTERNS.search(nl):
                        has_db_in_loop = True
                        break
                if has_db_in_loop:
                    break
            if not has_db_in_loop:
                continue
            severity = "high"
            description = "N+1 query pattern — database call inside a loop"

        line_hint = matches[0].group(0).strip()[:80]
        risks.append(Risk(
            severity=severity,
            category=category,
            description=description,
            line_hint=line_hint,
            suggestion=suggestion,
        ))

    # Sort by severity
    severity_order = {"high": 0, "medium": 1, "low": 2}
    risks.sort(key=lambda r: severity_order.get(r.severity, 3))

    return risks


def format_risk_report(risks: list[Risk]) -> str:
    """Format risks as a markdown section."""
    if not risks:
        return (
            "### 🛡️ Pre-Test Risk Analysis\n\n"
            "> No performance anti-patterns detected in the diff\n"
        )

    lines = ["### 🛡️ Pre-Test Risk Analysis\n"]

    high_count = sum(1 for r in risks if r.severity == "high")
    med_count = sum(1 for r in risks if r.severity == "medium")
    if high_count:
        lines.append(f"> ⚠️ **{high_count} high-severity** risk{'s' if high_count != 1 else ''} detected\n")
    elif med_count:
        lines.append(f"> 🔍 **{med_count} medium-severity** risk{'s' if med_count != 1 else ''} detected\n")

    severity_icons = {"high": "🔴", "medium": "🟡", "low": "🔵"}

    lines.append("| Severity | Risk | Suggestion |")
    lines.append("|----------|------|------------|")
    for r in risks:
        icon = severity_icons.get(r.severity, "⚪")
        lines.append(f"| {icon} {r.severity.upper()} | {r.description} | {r.suggestion} |")

    lines.append("")
    return "\n".join(lines)


def main():
    if "--diff-stdin" not in sys.argv:
        print("Usage: analyze-risk.py --diff-stdin < diff.patch", file=sys.stderr)
        sys.exit(1)

    diff_text = sys.stdin.read()
    if not diff_text.strip():
        print("No diff provided", file=sys.stderr)
        sys.exit(1)

    risks = analyze_diff(diff_text)
    report = format_risk_report(risks)
    print(report)


if __name__ == "__main__":
    main()
