"""Kassandra Simulator Configuration."""

import os

USE_ANTHROPIC = os.getenv("KASSANDRA_USE_ANTHROPIC", "0") == "1"

LOCAL_BASE_URL = os.getenv("KASSANDRA_LOCAL_URL", "http://localhost:8080/v1")
LOCAL_MODEL = os.getenv("KASSANDRA_LOCAL_MODEL", "default")

ANTHROPIC_MODEL = os.getenv("KASSANDRA_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYSTEM_PROMPT_PATH = os.path.join(REPO_ROOT, "prompts", "kassandra-system.md")
OUTPUT_DIR = os.path.join(REPO_ROOT, "simulator", "output")

MAX_TOOL_ROUNDS = 20
K6_TIMEOUT = 300

PROJECT = os.getenv("KASSANDRA_PROJECT", "quickpizza")

_PROJECT_DEFAULTS = {
    "quickpizza": {
        "review_url": "http://localhost:3333",
        "project_dir": "demos/quickpizza",
        "samples_dir": os.path.join(REPO_ROOT, "samples", "quickpizza"),
    },
    "pageturn": {
        "review_url": "http://localhost:8000",
        "project_dir": "demos/pageturn",
        "samples_dir": os.path.join(REPO_ROOT, "samples", "pageturn"),
    },
}

_project_cfg = _PROJECT_DEFAULTS.get(PROJECT, _PROJECT_DEFAULTS["quickpizza"])
REVIEW_ENV_URL = os.getenv("KASSANDRA_REVIEW_URL", _project_cfg["review_url"])
PROJECT_DIR = os.getenv("KASSANDRA_PROJECT_DIR", _project_cfg["project_dir"])
SAMPLES_DIR = os.getenv("KASSANDRA_SAMPLES_DIR", _project_cfg["samples_dir"])
