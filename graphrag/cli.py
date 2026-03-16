#!/usr/bin/env python3
"""CLI entry point for OpenAPI GraphRAG — used by Kassandra agent on GitLab runner.

Usage:
    python3 graphrag/cli.py --spec path/to/openapi.json --diff-stdin <<'DIFF'
    <unified diff content>
    DIFF

Outputs:
    1. Graph traversal visualization (which nodes/edges were visited)
    2. Retrieved API context (schemas, parameters, auth requirements)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .builder import OpenAPIGraph
from .retriever import SubgraphRetriever


def _format_traversal(graph: OpenAPIGraph, retriever: SubgraphRetriever, endpoints: list[str], context) -> str:
    """Format a visual representation of the graph traversal."""
    G = graph.graph
    lines = []
    lines.append("## GraphRAG Traversal\n")
    lines.append(f"Graph: {graph.stats()['nodes']} nodes, {graph.stats()['edges']} edges")
    lines.append(f"Matched endpoints: {len(endpoints)}\n")

    for ep in endpoints:
        if not G.has_node(ep):
            lines.append(f"  ✗ {ep} (not found in spec)")
            continue

        ep_data = G.nodes[ep]
        lines.append(f"  ● {ep_data.get('method', '?')} {ep_data.get('path', '?')}")

        # Show edges from this endpoint
        for _, neighbor, edge_data in G.edges(ep, data=True):
            rel = edge_data.get("relation", "")
            if rel == "RETURNS":
                lines.append(f"    ├─ RETURNS → {neighbor} (schema)")
                _format_schema_tree(G, neighbor, lines, depth=2, indent="    │  ")
            elif rel == "ACCEPTS":
                lines.append(f"    ├─ ACCEPTS → {neighbor} (schema)")
                _format_schema_tree(G, neighbor, lines, depth=2, indent="    │  ")
            elif rel == "REQUIRES_AUTH":
                lines.append(f"    ├─ REQUIRES_AUTH → {neighbor} (security)")
            elif rel == "HAS_PARAM":
                param_data = G.nodes[neighbor]
                lines.append(f"    ├─ HAS_PARAM → {param_data.get('name', neighbor)} ({param_data.get('location', 'query')})")

        lines.append("")

    # Summary
    lines.append(f"Retrieved: {len(context.schemas)} schemas, {len(context.parameters)} params, auth={'yes' if context.requires_auth else 'no'}")

    return "\n".join(lines)


def _format_schema_tree(G, schema_name: str, lines: list[str], depth: int, indent: str, visited: set | None = None) -> None:
    """Recursively format schema properties and references."""
    if visited is None:
        visited = set()
    if schema_name in visited or depth <= 0:
        return
    visited.add(schema_name)

    if not G.has_node(schema_name):
        return

    for _, neighbor, edge_data in G.edges(schema_name, data=True):
        rel = edge_data.get("relation", "")
        if rel == "HAS_PROPERTY":
            prop_data = G.nodes[neighbor]
            lines.append(f"{indent}├─ .{prop_data.get('name', neighbor.split('.')[-1])}: {prop_data.get('property_type', '?')}")
        elif rel == "REFERENCES":
            lines.append(f"{indent}└─ REFERENCES → {neighbor}")
            _format_schema_tree(G, neighbor, lines, depth - 1, indent + "   ", visited)


def main():
    parser = argparse.ArgumentParser(description="OpenAPI GraphRAG — retrieve relevant API context from a diff")
    parser.add_argument("--spec", required=True, help="Path to OpenAPI JSON spec")
    parser.add_argument("--diff-stdin", action="store_true", help="Read unified diff from stdin")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output as JSON instead of text")
    args = parser.parse_args()

    # Load spec
    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"Error: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    with open(spec_path) as f:
        spec = json.load(f)

    # Build graph
    graph = OpenAPIGraph.from_spec(spec)

    # Read diff
    if args.diff_stdin:
        diff = sys.stdin.read()
    else:
        print("Error: --diff-stdin is required", file=sys.stderr)
        sys.exit(1)

    if not diff.strip():
        print("Error: empty diff on stdin", file=sys.stderr)
        sys.exit(1)

    # Retrieve context
    retriever = SubgraphRetriever(graph)
    endpoints = retriever.endpoints_from_diff(diff)

    if not endpoints:
        print("No matching endpoints found in diff.", file=sys.stderr)
        print("Falling back to full spec.", file=sys.stderr)
        sys.exit(2)  # Signal to agent: fall back to read_file openapi.json

    context = retriever.for_endpoints(endpoints)

    # Output
    if args.json_output:
        output = {
            "traversal": _format_traversal(graph, retriever, endpoints, context),
            "context": context.to_dict(),
        }
        print(json.dumps(output, indent=2))
    else:
        print(_format_traversal(graph, retriever, endpoints, context))
        print("\n---\n")
        print(context.to_text())


if __name__ == "__main__":
    main()
