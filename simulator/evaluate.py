"""
Kassandra Evaluator — Compare generated k6 scripts against gold-standard expected scripts.
"""

import argparse
import json
import re
import subprocess
from pathlib import Path

from . import config

REQUIRED_FEATURES = [
    "has_imports",
    "has_options",
    "has_scenarios",
    "has_thresholds",
    "has_default_function",
    "has_checks",
    "has_handle_summary",
]

OPTIONAL_FEATURES = [
    "has_smoke_scenario",
    "has_baseline_scenario",
    "has_auth",
    "has_tags",
    "has_groups",
    "has_custom_metrics",
    "has_sleep",
    "has_payload_variation",
]


def analyze_script(content: str) -> dict:
    features = {}

    features["has_imports"] = "import http from 'k6/http'" in content
    features["has_options"] = (
        "export const options" in content or "export let options" in content
    )
    features["has_scenarios"] = "scenarios:" in content or "scenarios :" in content
    features["has_thresholds"] = "thresholds:" in content or "thresholds :" in content
    features["has_default_function"] = "export default function" in content
    features["has_checks"] = "check(" in content
    features["has_handle_summary"] = "handleSummary" in content

    features["has_smoke_scenario"] = (
        "smoke" in content.lower() and "scenario" in content.lower()
    )
    features["has_baseline_scenario"] = "baseline" in content.lower()
    features["has_auth"] = (
        "Authorization" in content
        or "loginAndGetToken" in content
        or "getAuthHeaders" in content
    )
    features["has_tags"] = "tags:" in content or "tags :" in content
    features["has_groups"] = "group(" in content
    features["has_custom_metrics"] = "new Rate(" in content or "new Trend(" in content
    features["has_sleep"] = "sleep(" in content
    features["has_payload_variation"] = (
        "Math.random()" in content
        or "randomItem" in content
        or any(pat in content for pat in ["BATCH_SIZES", "PERIODS", "LIMITS"])
    )

    executor_match = re.search(r"executor:\s*['\"]([^'\"]+)['\"]", content)
    features["executor"] = executor_match.group(1) if executor_match else None

    endpoint_matches = re.findall(
        r"tags:\s*\{[^}]*endpoint:\s*['\"]([^'\"]+)['\"]", content
    )
    features["endpoints_tested"] = list(set(endpoint_matches))

    check_matches = re.findall(r"check\(", content)
    features["check_count"] = len(check_matches)

    return features


def k6_inspect(script_path: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["k6", "inspect", script_path],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=config.REPO_ROOT,
        )
        return result.returncode == 0, result.stderr or result.stdout
    except FileNotFoundError:
        return False, "k6 not found in PATH"
    except subprocess.TimeoutExpired:
        return False, "k6 inspect timed out"


def evaluate_script(
    generated_path: str,
    expected_path: str | None = None,
    verbose: bool = False,
) -> dict:
    gen_path = Path(generated_path)
    if not gen_path.exists():
        return {"error": f"Generated script not found: {generated_path}", "score": 0}

    gen_content = gen_path.read_text()
    gen_features = analyze_script(gen_content)

    result = {
        "generated": str(gen_path),
        "features": gen_features,
        "issues": [],
        "score": 0,
        "max_score": 0,
    }

    for feat in REQUIRED_FEATURES:
        result["max_score"] += 2
        if gen_features.get(feat):
            result["score"] += 2
        else:
            result["issues"].append(f"Missing required: {feat}")

    for feat in OPTIONAL_FEATURES:
        result["max_score"] += 1
        if gen_features.get(feat):
            result["score"] += 1

    result["max_score"] += 3
    compiles, inspect_output = k6_inspect(generated_path)
    result["compiles"] = compiles
    if compiles:
        result["score"] += 3
    else:
        result["issues"].append(f"Does not compile: {inspect_output[:200]}")

    if expected_path:
        exp_path = Path(expected_path)
        if exp_path.exists():
            exp_content = exp_path.read_text()
            exp_features = analyze_script(exp_content)
            result["expected_features"] = exp_features

            result["max_score"] += 2
            if gen_features.get("executor") == exp_features.get("executor"):
                result["score"] += 2
            else:
                result["issues"].append(
                    f"Executor mismatch: got {gen_features.get('executor')}, "
                    f"expected {exp_features.get('executor')}"
                )

            result["max_score"] += 2
            gen_endpoints = set(gen_features.get("endpoints_tested", []))
            exp_endpoints = set(exp_features.get("endpoints_tested", []))
            overlap = gen_endpoints & exp_endpoints
            if exp_endpoints and len(overlap) / len(exp_endpoints) >= 0.5:
                result["score"] += 2
            else:
                result["issues"].append(
                    f"Low endpoint coverage: tested {gen_endpoints}, expected {exp_endpoints}"
                )

    result["percentage"] = (
        round(result["score"] / result["max_score"] * 100, 1)
        if result["max_score"] > 0
        else 0
    )

    return result


def evaluate_runtime(
    summary_path: str,
    slos: dict | None = None,
    verbose: bool = False,
) -> dict:
    """Evaluate k6 runtime results against SLO thresholds.

    Args:
        summary_path: Path to k6 summary.json output.
        slos: SLO overrides. Defaults to AGENTS.md values.
        verbose: Print detailed output.

    Returns:
        Dict with runtime evaluation results and pass/fail status.
    """
    if slos is None:
        slos = {
            "p95_ms": 2000,
            "p95_batch_ms": 5000,
            "p95_auth_ms": 1000,
            "error_rate": 0.005,
        }

    path = Path(summary_path)
    if not path.exists():
        return {"error": f"Summary not found: {summary_path}", "pass": False}

    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return {"error": f"Failed to parse summary: {e}", "pass": False}

    result = {
        "summary_path": str(path),
        "slos": slos,
        "metrics": {},
        "threshold_results": {},
        "issues": [],
        "pass": True,
    }

    # Extract core metrics from k6 summary JSON
    metrics = data.get("metrics", {})

    # Detect if test includes batch endpoints (use relaxed SLO for aggregate)
    has_batch_endpoints = any(
        "batch" in key.lower()
        for key in metrics
        if key.startswith("http_req_duration{") or key.startswith("batch")
    )

    # HTTP request duration
    http_dur = metrics.get("http_req_duration", {})
    if http_dur:
        values = http_dur.get("values", {})
        result["metrics"]["http_req_duration"] = {
            "p95": values.get("p(95)"),
            "p99": values.get("p(99)"),
            "avg": values.get("avg"),
            "med": values.get("med"),
            "min": values.get("min"),
            "max": values.get("max"),
        }

        p95 = values.get("p(95)")
        if p95 is not None:
            # Use batch SLO for aggregate if batch endpoints are present
            effective_slo = (
                slos["p95_batch_ms"] if has_batch_endpoints else slos["p95_ms"]
            )
            passed = p95 < effective_slo
            result["threshold_results"]["p95_latency"] = {
                "value": round(p95, 2),
                "threshold": effective_slo,
                "pass": passed,
            }
            if not passed:
                result["issues"].append(
                    f"p95 latency {p95:.0f}ms exceeds SLO {effective_slo}ms"
                )
                result["pass"] = False

    # HTTP request failure rate
    http_failed = metrics.get("http_req_failed", {})
    if http_failed:
        values = http_failed.get("values", {})
        fail_rate = values.get("rate", 0)
        result["metrics"]["http_req_failed"] = {"rate": fail_rate}
        passed = fail_rate < slos["error_rate"]
        result["threshold_results"]["error_rate"] = {
            "value": round(fail_rate, 4),
            "threshold": slos["error_rate"],
            "pass": passed,
        }
        if not passed:
            result["issues"].append(
                f"Error rate {fail_rate:.2%} exceeds SLO {slos['error_rate']:.2%}"
            )
            result["pass"] = False

    # Requests per second
    http_reqs = metrics.get("http_reqs", {})
    if http_reqs:
        values = http_reqs.get("values", {})
        result["metrics"]["http_reqs"] = {
            "count": values.get("count"),
            "rate": round(values.get("rate", 0), 2),
        }

    # Check per-endpoint metrics (tagged thresholds)
    for key, metric in metrics.items():
        if not key.startswith("http_req_duration{"):
            continue
        values = metric.get("values", {})
        p95 = values.get("p(95)")
        if p95 is None:
            continue

        # Determine which SLO applies
        threshold = slos["p95_ms"]
        if has_batch_endpoints and "expected_response" in key.lower():
            # Aggregate of all successful responses — use batch SLO when batch is present
            threshold = slos["p95_batch_ms"]
        elif "batch" in key.lower():
            threshold = slos["p95_batch_ms"]
        elif "auth" in key.lower() or "login" in key.lower():
            threshold = slos["p95_auth_ms"]

        passed = p95 < threshold
        label = key.replace("http_req_duration", "").strip("{}")
        result["threshold_results"][f"p95_{label}"] = {
            "value": round(p95, 2),
            "threshold": threshold,
            "pass": passed,
        }
        if not passed:
            result["issues"].append(
                f"p95 {label} {p95:.0f}ms exceeds SLO {threshold}ms"
            )
            result["pass"] = False

    # Check k6's own threshold results if present
    root_thresholds = data.get("root_group", {}).get("checks", [])
    checks_passed = 0
    checks_total = 0
    for check in root_thresholds:
        checks_total += check.get("passes", 0) + check.get("fails", 0)
        checks_passed += check.get("passes", 0)
    if checks_total > 0:
        result["metrics"]["checks"] = {
            "passed": checks_passed,
            "total": checks_total,
            "rate": round(checks_passed / checks_total, 4),
        }

    return result


def evaluate_session(
    session_dir: str | None = None,
    verbose: bool = False,
) -> dict:
    """Evaluate a full simulator session: static analysis + runtime results.

    Finds the most recent generated k6 script and summary.json, then runs
    both static and runtime evaluation.
    """
    project_root = Path(config.REPO_ROOT)
    if config.PROJECT_DIR:
        project_root = project_root / config.PROJECT_DIR
    kassandra_dir = project_root / "k6" / "kassandra"

    result = {"static": None, "runtime": None, "issues": []}

    # Find the most recent generated script
    scripts = sorted(kassandra_dir.glob("mr-*.js"), key=lambda p: p.stat().st_mtime)
    if scripts:
        latest_script = scripts[-1]
        result["static"] = evaluate_script(str(latest_script), verbose=verbose)
        if verbose:
            print(f"Static evaluation: {latest_script.name}")
            print(f"  Score: {result['static']['percentage']}%")
    else:
        result["issues"].append("No generated k6 scripts found in k6/kassandra/")

    # Find the most recent summary.json
    results_dir = kassandra_dir / "results"
    summaries = (
        sorted(results_dir.glob("*summary*.json"), key=lambda p: p.stat().st_mtime)
        if results_dir.exists()
        else []
    )
    if summaries:
        latest_summary = summaries[-1]
        result["runtime"] = evaluate_runtime(str(latest_summary), verbose=verbose)
        if verbose:
            print(f"Runtime evaluation: {latest_summary.name}")
            print(f"  Pass: {result['runtime']['pass']}")
    else:
        result["issues"].append(
            "No k6 summary.json found — k6 may not have run or handleSummary() is missing"
        )

    # Overall verdict
    static_ok = result["static"] and result["static"].get("percentage", 0) >= 70
    runtime_ok = result["runtime"] and result["runtime"].get("pass", False)
    runtime_missing = result["runtime"] is None

    if static_ok and runtime_ok:
        result["verdict"] = "PASS"
    elif static_ok and runtime_missing:
        result["verdict"] = "PARTIAL — script looks good but no runtime results"
    elif static_ok and not runtime_ok:
        result["verdict"] = "FAIL — script valid but SLOs breached"
    else:
        result["verdict"] = "FAIL"

    return result


def check_all_expected(verbose: bool = False):
    project_root = Path(config.REPO_ROOT)
    if config.PROJECT_DIR:
        project_root = project_root / config.PROJECT_DIR
    expected_dir = project_root / "k6" / "foundations"
    results = []
    for script in sorted(expected_dir.glob("*.js")):
        print(f"\nChecking: {script.name}")
        result = evaluate_script(str(script), verbose=verbose)
        results.append(result)

        status = (
            "PASS"
            if result["percentage"] >= 80
            else "WARN"
            if result["percentage"] >= 60
            else "FAIL"
        )
        print(
            f"  Score: {result['score']}/{result['max_score']} ({result['percentage']}%) [{status}]"
        )
        if result.get("compiles") is False:
            print("  DOES NOT COMPILE")
        for issue in result["issues"]:
            print(f"  Issue: {issue}")

    total = sum(r["score"] for r in results)
    max_total = sum(r["max_score"] for r in results)
    print(f"\nOverall: {total}/{max_total} ({round(total / max_total * 100, 1)}%)")
    return results


def main():
    parser = argparse.ArgumentParser(description="Kassandra Script Evaluator")
    parser.add_argument("generated", nargs="?", help="Path to generated k6 script")
    parser.add_argument("expected", nargs="?", help="Path to expected k6 script")
    parser.add_argument(
        "--check-all", action="store_true", help="Check all expected scripts"
    )
    parser.add_argument(
        "--session",
        action="store_true",
        help="Evaluate the latest simulator session (static + runtime)",
    )
    parser.add_argument(
        "--runtime",
        metavar="SUMMARY_JSON",
        help="Evaluate k6 summary.json against SLOs",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.session:
        result = evaluate_session(verbose=args.verbose)
        print(f"\nVerdict: {result['verdict']}")
        if result["static"]:
            print(f"  Static score: {result['static']['percentage']}%")
            for issue in result["static"].get("issues", []):
                print(f"    - {issue}")
        if result["runtime"]:
            print(f"  Runtime pass: {result['runtime']['pass']}")
            for tr_name, tr in result["runtime"].get("threshold_results", {}).items():
                status = "PASS" if tr["pass"] else "FAIL"
                print(
                    f"    [{status}] {tr_name}: {tr['value']} (threshold: {tr['threshold']})"
                )
            for issue in result["runtime"].get("issues", []):
                print(f"    - {issue}")
        for issue in result.get("issues", []):
            print(f"  - {issue}")
        print(json.dumps(result, indent=2) if args.verbose else "")
    elif args.runtime:
        result = evaluate_runtime(args.runtime, verbose=args.verbose)
        print(json.dumps(result, indent=2))
    elif args.check_all:
        check_all_expected(verbose=args.verbose)
    elif args.generated:
        result = evaluate_script(args.generated, args.expected, verbose=args.verbose)
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
