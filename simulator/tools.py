"""
Local tool implementations that mirror GitLab Duo Agent Platform tools.

Each tool function takes keyword arguments and returns a string result.
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import config

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file in the repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to repo root",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Find files matching a glob pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern (e.g., '**/*.js')",
                    }
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search for a pattern in files. Returns matching lines with file paths.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command. Use for running k6, validating scripts, etc.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create or overwrite a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_mr_note",
            "description": "Post a markdown note/comment to the merge request.",
            "parameters": {
                "type": "object",
                "properties": {"body": {"type": "string"}},
                "required": ["body"],
            },
        },
    },
]

# Anthropic tool format (converted from OpenAI)
ANTHROPIC_TOOLS = [
    {
        "name": t["function"]["name"],
        "description": t["function"]["description"],
        "input_schema": t["function"]["parameters"],
    }
    for t in TOOLS
]


def execute_tool(name: str, arguments: dict) -> str:
    """Dispatch a tool call to the appropriate handler."""
    handlers = {
        "read_file": _read_file,
        "find_files": _find_files,
        "grep": _grep,
        "run_command": _run_command,
        "create_file": _create_file,
        "create_mr_note": _create_mr_note,
    }
    handler = handlers.get(name)
    if not handler:
        return f"Error: Unknown tool '{name}'"
    try:
        return handler(**arguments)
    except Exception as e:
        return f"Error executing {name}: {e}"


def _read_file(path: str) -> str:
    """Read a file from the repo directory."""
    full_path = Path(config.REPO_ROOT) / path
    if not full_path.exists():
        return f"Error: File not found: {path}"
    if not full_path.is_file():
        return f"Error: Not a file: {path}"
    try:
        content = full_path.read_text(encoding="utf-8")
        if len(content) > 50_000:
            return content[:50_000] + "\n... (truncated, file too large)"
        return content
    except Exception as e:
        return f"Error reading {path}: {e}"


def _find_files(pattern: str) -> str:
    """Find files matching a glob pattern."""
    root = Path(config.REPO_ROOT)
    matches = sorted(str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file())
    if not matches:
        return f"No files matching pattern: {pattern}"
    if len(matches) > 100:
        return "\n".join(matches[:100]) + f"\n... ({len(matches)} total, showing first 100)"
    return "\n".join(matches)


def _grep(pattern: str, path: str = ".") -> str:
    """Search for a pattern in files."""
    search_path = Path(config.REPO_ROOT) / path
    if not search_path.exists():
        return f"Error: Path not found: {path}"
    try:
        result = subprocess.run(
            ["grep", "-rn", "--include=*.js", "--include=*.ts", "--include=*.go",
             "--include=*.py", "--include=*.md", "--include=*.json", "--include=*.yaml",
             "--include=*.yml", pattern, str(search_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        if not output:
            return f"No matches found for pattern: {pattern}"
        # Make paths relative to repo root
        output = output.replace(str(config.REPO_ROOT) + "/", "")
        lines = output.split("\n")
        if len(lines) > 50:
            return "\n".join(lines[:50]) + f"\n... ({len(lines)} total matches, showing first 50)"
        return output
    except subprocess.TimeoutExpired:
        return "Error: grep timed out after 30 seconds"


def _run_command(command: str) -> str:
    """Execute a shell command."""
    # Safety: block dangerous commands
    blocked = ["rm -rf /", "mkfs", "dd if=", "> /dev/"]
    for b in blocked:
        if b in command:
            return f"Error: Blocked dangerous command pattern: {b}"
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=config.K6_TIMEOUT,
            cwd=config.REPO_ROOT,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += "\nSTDERR:\n" + result.stderr
        if result.returncode != 0:
            output += f"\n(exit code: {result.returncode})"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {config.K6_TIMEOUT} seconds"


def _create_file(path: str, content: str) -> str:
    """Create or overwrite a file in the repo directory."""
    full_path = Path(config.REPO_ROOT) / path
    # Safety: don't write outside repo
    try:
        full_path.resolve().relative_to(Path(config.REPO_ROOT).resolve())
    except ValueError:
        return f"Error: Cannot write outside repository: {path}"
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return f"File created: {path} ({len(content)} bytes)"


def _create_mr_note(body: str) -> str:
    """Simulate posting an MR note by writing to output directory."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_path = Path(config.OUTPUT_DIR) / f"mr-note-{timestamp}.md"
    output_path.write_text(body, encoding="utf-8")
    # Print the note with formatting
    print("\n" + "=" * 60)
    print("  MR NOTE (simulated)")
    print("=" * 60)
    print(body)
    print("=" * 60 + "\n")
    return f"MR note posted successfully. Saved to: {output_path.relative_to(Path(config.REPO_ROOT))}"
