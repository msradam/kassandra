#!/usr/bin/env bash
# Thin wrapper to run GraphRAG with the correct Python version.
# The GitLab runner's default python3 is 3.6 which can't run the module.
# Usage: echo "<diff>" | bash scripts/run-graphrag.sh --spec path/to/openapi.json --diff-stdin
set -euo pipefail
GRAPHRAG_PYTHON=$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3)
exec "$GRAPHRAG_PYTHON" -m graphrag "$@"
