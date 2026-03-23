"""
A/B test: full OpenAPI spec vs GraphRAG context for k6 test generation.

Sends the same prompt to Claude twice per endpoint — once with the full spec,
once with only the GraphRAG-retrieved subgraph. Compares input tokens, schema
field coverage, and hallucinated endpoints.

Usage:
    ANTHROPIC_API_KEY=sk-... uv run python scripts/graphrag-proof.py
"""

import json
import os
import sys
import time

# Ensure project root is on the path when run as `uv run python scripts/graphrag-proof.py`
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import anthropic

from graphrag.builder import OpenAPIGraph
from graphrag.retriever import SubgraphRetriever

MODEL = "claude-sonnet-4-20250514"
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

SYSTEM = (
    "You are a k6 load test generator. Given an API spec context and a target endpoint, "
    "write a k6 script that tests ONLY the specified endpoint. Include deep response validation "
    "(check status, content-type, response body fields and types). Use constant-arrival-rate executor. "
    "Output ONLY the k6 JavaScript code, no explanation."
)

TESTS = [
    {
        "app": "Midas Bank",
        "spec": "demos/midas-bank/openapi.json",
        "endpoint": "GET /api/accounts/{account_id}/statement",
        "endpoint_path": "/api/accounts/{account_id}/statement",
        "prompt_detail": "Requires Bearer token auth. Test with account_id=1, days=30.",
        "schema_fields": [
            "account_id", "account_name", "period_start", "period_end",
            "opening_balance", "closing_balance", "entries",
            "date", "description", "amount", "direction", "balance_after",
        ],
    },
    {
        "app": "Calliope Books",
        "spec": "demos/calliope-books/openapi.json",
        "endpoint": "GET /api/books/{id}/recommendations",
        "endpoint_path": "/api/books/{id}/recommendations",
        "prompt_detail": "Test with book id=1, limit=5. No auth required.",
        "schema_fields": [
            "source_book", "by_author", "by_genre", "top_rated", "total",
            "id", "title", "author", "genre", "avg_rating", "review_count",
        ],
    },
    {
        "app": "Hestia Eats",
        "spec": "demos/hestia-eats/openapi.json",
        "endpoint": "GET /api/promotions/{promotion_id}",
        "endpoint_path": "/api/promotions/{promotion_id}",
        "prompt_detail": "No auth required. Test with promotion_id=promo-1.",
        "schema_fields": [
            "id", "restaurant_id", "title", "description", "discount_pct",
            "min_order", "promo_code", "is_active", "starts_at", "expires_at",
            "restaurant", "name", "cuisine", "rating", "menu_items", "price", "category",
        ],
    },
]


def find_hallucinated_endpoints(code: str, all_paths: list[str], target_path: str) -> list[str]:
    """Find API paths in generated code that aren't the target endpoint."""
    hallucinated = []
    target_base = target_path.split("{")[0].rstrip("/")

    for path in all_paths:
        if path == target_path:
            continue
        path_base = path.split("{")[0].rstrip("/")
        if not path_base or len(path_base) <= 5:
            continue
        # Skip parent paths that are substrings of the target
        if target_base.startswith(path_base):
            continue
        if path_base in code:
            hallucinated.append(path)
    return hallucinated


def run_test(test_config: dict) -> dict:
    """Run A/B comparison for one endpoint."""
    spec = json.load(open(test_config["spec"]))
    full_spec_text = json.dumps(spec, indent=2)
    all_paths = list(spec.get("paths", {}).keys())

    # Build graph and retrieve subgraph
    graph = OpenAPIGraph.from_spec(spec)
    retriever = SubgraphRetriever(graph)
    ctx = retriever.for_endpoints([test_config["endpoint_path"]])
    graphrag_text = ctx.to_text()

    print(f"\n{'=' * 60}")
    print(f"  {test_config['app']}: {test_config['endpoint']}")
    print(f"{'=' * 60}")
    print(f"  Graph: {graph.graph.number_of_nodes()} nodes, {graph.graph.number_of_edges()} edges")
    print(f"  Full spec: {len(full_spec_text):,} chars | GraphRAG: {len(graphrag_text):,} chars")

    prompt = (
        f"Generate a k6 load test for: {test_config['endpoint']}\n\n"
        f"API Context:\n{{context}}\n\n"
        f"{test_config['prompt_detail']}\n"
        f"Validate all response fields match the schema."
    )

    # A: Full spec
    print(f"  Running A (full spec)...")
    t0 = time.time()
    resp_a = client.messages.create(
        model=MODEL, max_tokens=4096, system=SYSTEM,
        messages=[{"role": "user", "content": prompt.replace("{context}", full_spec_text)}],
    )
    time_a = time.time() - t0
    code_a = resp_a.content[0].text

    # B: GraphRAG
    print(f"  Running B (GraphRAG)...")
    t0 = time.time()
    resp_b = client.messages.create(
        model=MODEL, max_tokens=4096, system=SYSTEM,
        messages=[{"role": "user", "content": prompt.replace("{context}", graphrag_text)}],
    )
    time_b = time.time() - t0
    code_b = resp_b.content[0].text

    # Compare results
    hall_a = find_hallucinated_endpoints(code_a, all_paths, test_config["endpoint_path"])
    hall_b = find_hallucinated_endpoints(code_b, all_paths, test_config["endpoint_path"])
    fields = test_config["schema_fields"]
    cov_a = sum(1 for f in fields if f in code_a)
    cov_b = sum(1 for f in fields if f in code_b)

    token_reduction = 100 - (resp_b.usage.input_tokens / resp_a.usage.input_tokens * 100)

    print(f"\n  {'Metric':<28} {'Full Spec':>12} {'GraphRAG':>12}")
    print(f"  {'─' * 54}")
    print(f"  {'Input tokens':<28} {resp_a.usage.input_tokens:>12,} {resp_b.usage.input_tokens:>12,}  ({token_reduction:.1f}% reduction)")
    print(f"  {'Output tokens':<28} {resp_a.usage.output_tokens:>12,} {resp_b.usage.output_tokens:>12,}")
    print(f"  {'Latency (s)':<28} {time_a:>12.1f} {time_b:>12.1f}")
    print(f"  {'Schema fields covered':<28} {cov_a:>12}/{len(fields)} {cov_b:>12}/{len(fields)}")
    print(f"  {'Hallucinated endpoints':<28} {len(hall_a):>12} {len(hall_b):>12}")

    if hall_a:
        print(f"  Full spec hallucinations: {hall_a}")
    if hall_b:
        print(f"  GraphRAG hallucinations:  {hall_b}")

    # Save generated scripts
    slug = test_config["app"].lower().replace(" ", "-")
    os.makedirs("k6/kassandra/results", exist_ok=True)
    with open(f"k6/kassandra/results/proof-{slug}-full.js", "w") as f:
        f.write(code_a)
    with open(f"k6/kassandra/results/proof-{slug}-graphrag.js", "w") as f:
        f.write(code_b)

    return {
        "app": test_config["app"],
        "token_reduction": token_reduction,
        "coverage_full": cov_a,
        "coverage_graphrag": cov_b,
        "total_fields": len(fields),
        "hallucinations_full": len(hall_a),
        "hallucinations_graphrag": len(hall_b),
        "hallucination_details": hall_a,
    }


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY environment variable.")
        sys.exit(1)

    print(f"GraphRAG A/B Test — Model: {MODEL}")
    print(f"Tests: {len(TESTS)} endpoints across {len(TESTS)} demo apps")

    results = []
    for test in TESTS:
        results.append(run_test(test))

    # Summary
    print(f"\n{'=' * 60}")
    print("  SUMMARY")
    print(f"{'=' * 60}")
    for r in results:
        print(f"\n  {r['app']}:")
        print(f"    Token reduction:     {r['token_reduction']:.1f}%")
        print(f"    Schema coverage:     {r['coverage_full']}/{r['total_fields']} (full) vs {r['coverage_graphrag']}/{r['total_fields']} (graphrag)")
        print(f"    Hallucinated endpoints: {r['hallucinations_full']} (full) vs {r['hallucinations_graphrag']} (graphrag)")

    avg_token = sum(r["token_reduction"] for r in results) / len(results)
    total_hall_full = sum(r["hallucinations_full"] for r in results)
    total_hall_graphrag = sum(r["hallucinations_graphrag"] for r in results)
    print(f"\n  Average token reduction: {avg_token:.1f}%")
    print(f"  Total hallucinated endpoints: {total_hall_full} (full spec) vs {total_hall_graphrag} (graphrag)")
    print(f"\n  Generated scripts saved to k6/kassandra/results/proof-*.js")

    # Save summary to file
    output_path = "scripts/graphrag-proof-output.txt"
    with open(output_path, "w") as f:
        f.write(f"GraphRAG A/B Test Results\n")
        f.write(f"Model: {MODEL}\n")
        f.write(f"Date: {time.strftime('%Y-%m-%d')}\n\n")
        for r in results:
            f.write(f"{r['app']}:\n")
            f.write(f"  Token reduction:        {r['token_reduction']:.1f}%\n")
            f.write(f"  Schema coverage (full): {r['coverage_full']}/{r['total_fields']}\n")
            f.write(f"  Schema coverage (RAG):  {r['coverage_graphrag']}/{r['total_fields']}\n")
            f.write(f"  Hallucinations (full):  {r['hallucinations_full']}\n")
            f.write(f"  Hallucinations (RAG):   {r['hallucinations_graphrag']}\n")
            if r["hallucination_details"]:
                f.write(f"  Hallucinated paths:     {r['hallucination_details']}\n")
            f.write("\n")
        f.write(f"Average token reduction: {avg_token:.1f}%\n")
        f.write(f"Total hallucinations: {total_hall_full} (full) vs {total_hall_graphrag} (graphrag)\n")
    print(f"  Results saved to {output_path}")
