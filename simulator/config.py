"""
Kassandra Simulator Configuration.

Switch between local MLX model and Anthropic API.
Default: local MLX via OpenAI-compatible endpoint.
Set KASSANDRA_USE_ANTHROPIC=1 for Anthropic (requires ANTHROPIC_API_KEY).
"""

import os

USE_ANTHROPIC = os.getenv("KASSANDRA_USE_ANTHROPIC", "0") == "1"

# Local MLX model (OpenAI-compatible server)
LOCAL_BASE_URL = os.getenv("KASSANDRA_LOCAL_URL", "http://localhost:8080/v1")
LOCAL_MODEL = os.getenv("KASSANDRA_LOCAL_MODEL", "default")

# Anthropic API
ANTHROPIC_MODEL = os.getenv("KASSANDRA_ANTHROPIC_MODEL", "claude-sonnet-4-5-20250514")

# Paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM_PROMPT_PATH = os.path.join(REPO_ROOT, "prompts", "kassandra-system.md")
SAMPLES_DIR = os.path.join(REPO_ROOT, "samples")
OUTPUT_DIR = os.path.join(REPO_ROOT, "simulator", "output")

# Limits
MAX_TOOL_ROUNDS = 20
K6_TIMEOUT = 180

# Review environment
REVIEW_ENV_URL = os.getenv("KASSANDRA_REVIEW_URL", "https://quickpizza.grafana.com")
