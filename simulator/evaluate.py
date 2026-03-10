"""
Kassandra Evaluator — Compare generated k6 scripts against gold-standard expected scripts.

Usage:
    uv run python -m simulator.evaluate tests/k6/kassandra/mr-42-batch-recommendation.js samples/expected/01-batch-endpoint.js
    uv run python -m simulator.evaluate --check-all
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from . import config

# Expected features in a well-formed Kassandra k6 script
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
    """Analyze a k6 script and extract features."""
    features = {}

    # Required
    features["has_imports"] = "import http from 'k6/http'" in content
    features["has_options"] = "export const options" in content or "export let options" in content
    features["has_scenarios"] = "scenarios:" in content or "scenarios :" in content
    features["has_thresholds"] = "thresholds:" in content or "thresholds :" in content
    features["has_default_function"] = "export default function" in content
    features["has_checks"] = "check(" in content
    features["has_handle_summary"] = "handleSummary" in content

    # Optional
    features["has_smoke_scenario"] = "smoke" in content.lower() and "scenario" in content.lower()
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

    # Extract executor
    executor_match = re.search(r"executor:\s*['\"]([^'\"]+)['\"]", content)
    features["executor"] = executor_match.group(1) if executor_match else None

    # Count endpoints tested
    endpoint_matches = re.findall(r"tags:\s*\{[^}]*endpoint:\s*['\"]([^'\"]+)['\"]", content)
    features["endpoints_tested"] = list(set(endpoint_matches))

    # Count check assertions
    check_matches = re.findall(r"check\(", content)
    features["check_count"] = len(check_matches)

    return features


def k6_inspect(script_path: str) -> tuple[bool, str]:
    """Run k6 inspect to verify script compiles."""
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
    """Evaluate a generated k6 script."""
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

    # Check required features (2 points each)
    for feat in REQUIRED_FEATURES:
        result["max_score"] += 2
        if gen_features.get(feat):
            result["score"] += 2
        else:
            result["issues"].append(f"Missing required: {feat}")

    # Check optional features (1 point each)
    for feat in OPTIONAL_FEATURES:
        result["max_score"] += 1
        if gen_features.get(feat):
            result["score"] += 1

    # k6 inspect (3 points)
    result["max_score"] += 3
    compiles, inspect_output = k6_inspect(generated_path)
    result["compiles"] = compiles
    if compiles:
        result["score"] += 3
    else:
        result["issues"].append(f"Does not compile: {inspect_output[:200]}")

    # Compare against expected (if provided)
    if expected_path:
        exp_path = Path(expected_path)
        if exp_path.exists():
            exp_content = exp_path.read_text()
            exp_features = analyze_script(exp_content)
            result["expected_features"] = exp_features

            # Executor match (2 points)
            result["max_score"] += 2
            if gen_features.get("executor") == exp_features.get("executor"):
                result["score"] += 2
            else:
                result["issues"].append(
                    f"Executor mismatch: got {gen_features.get('executor')}, "
                    f"expected {exp_features.get('executor')}"
                )

            # Similar endpoint coverage (2 points)
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

    # Final percentage
    result["percentage"] = (
        round(result["score"] / result["max_score"] * 100, 1)
        if result["max_score"] > 0
        else 0
    )

    return result


def check_all_expected(verbose: bool = False):
    """Check all expected scripts compile and have good features."""
    expected_dir = Path(config.SAMPLES_DIR) / "expected"
    results = []
    for script in sorted(expected_dir.glob("*.js")):
        print(f"\nChecking: {script.name}")
        result = evaluate_script(str(script), verbose=verbose)
        results.append(result)

        status = "PASS" if result["percentage"] >= 80 else "WARN" if result["percentage"] >= 60 else "FAIL"
        print(f"  Score: {result['score']}/{result['max_score']} ({result['percentage']}%) [{status}]")
        if result.get("compiles") is False:
            print(f"  DOES NOT COMPILE")
        for issue in result["issues"]:
            print(f"  Issue: {issue}")

    total = sum(r["score"] for r in results)
    max_total = sum(r["max_score"] for r in results)
    print(f"\nOverall: {total}/{max_total} ({round(total/max_total*100, 1)}%)")
    return results


def main():
    parser = argparse.ArgumentParser(description="Kassandra Script Evaluator")
    parser.add_argument("generated", nargs="?", help="Path to generated k6 script")
    parser.add_argument("expected", nargs="?", help="Path to expected k6 script")
    parser.add_argument("--check-all", action="store_true", help="Check all expected scripts")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.check_all:
        check_all_expected(verbose=args.verbose)
    elif args.generated:
        result = evaluate_script(args.generated, args.expected, verbose=args.verbose)
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
