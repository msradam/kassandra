"""Kassandra Simulator Configuration."""

import os

USE_ANTHROPIC = os.getenv("KASSANDRA_USE_ANTHROPIC", "0") == "1"

LOCAL_BASE_URL = os.getenv("KASSANDRA_LOCAL_URL", "http://localhost:8080/v1")
LOCAL_MODEL = os.getenv("KASSANDRA_LOCAL_MODEL", "default")

ANTHROPIC_MODEL = os.getenv("KASSANDRA_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT_YML_PATH = os.path.join(REPO_ROOT, "agents", "agent.yml")
OUTPUT_DIR = os.path.join(REPO_ROOT, "simulator", "output")
SAMPLES_DIR = os.path.join(REPO_ROOT, "simulator", "samples")

MAX_TOOL_ROUNDS = 20
K6_TIMEOUT = 300

PROJECT = os.getenv("KASSANDRA_PROJECT", "calliope-books")

_PROJECT_DEFAULTS = {
    "calliope-books": {
        "review_url": "http://localhost:3000",
        "project_dir": "demos/calliope-books",
    },
    "midas-bank": {
        "review_url": "http://localhost:8000",
        "project_dir": "demos/midas-bank",
    },
}

_project_cfg = _PROJECT_DEFAULTS.get(PROJECT, _PROJECT_DEFAULTS["calliope-books"])
REVIEW_ENV_URL = os.getenv("KASSANDRA_REVIEW_URL", _project_cfg["review_url"])
PROJECT_DIR = os.getenv("KASSANDRA_PROJECT_DIR", _project_cfg["project_dir"])
