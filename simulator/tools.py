"""
Local tool implementations that mirror GitLab Duo Agent Platform tools.
"""

import os
import re
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
            "name": "create_file_with_contents",
            "description": "Create or overwrite a file. After writing .js files, automatically validates with k6 inspect.",
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
            "name": "create_merge_request_note",
            "description": "Post a markdown note/comment to the merge request.",
            "parameters": {
                "type": "object",
                "properties": {"body": {"type": "string"}},
                "required": ["body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_merge_request_diffs",
            "description": "Get the diff for the current merge request.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_merge_request",
            "description": "Get metadata for the current merge request (IID, title, branches, author).",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_k6_from_openapi",
            "description": "Generate a k6 test skeleton from the project's OpenAPI spec. Returns a base script you can customize.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spec_path": {
                        "type": "string",
                        "description": "Path to OpenAPI spec file (e.g., openapi.yaml). Use find_files to locate it first.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_k6_script",
            "description": "Validate a k6 script using k6 inspect and a structural linter. Returns issues found.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the k6 script to validate",
                    }
                },
                "required": ["path"],
            },
        },
    },
]

ANTHROPIC_TOOLS = [
    {
        "name": t["function"]["name"],
        "description": t["function"]["description"],
        "input_schema": t["function"]["parameters"],
    }
    for t in TOOLS
]

_mr_context = {}


def set_mr_context(context: dict):
    global _mr_context
    _mr_context = context


def execute_tool(name: str, arguments: dict) -> str:
    handlers = {
        "read_file": _read_file,
        "find_files": _find_files,
        "grep": _grep,
        "run_command": _run_command,
        "create_file_with_contents": _create_file,
        "create_merge_request_note": _create_mr_note,
        "list_merge_request_diffs": _list_mr_diffs,
        "get_merge_request": _get_mr,
        "generate_k6_from_openapi": _generate_k6_from_openapi,
        "validate_k6_script": _validate_k6_script,
    }
    handler = handlers.get(name)
    if not handler:
        return f"Error: Unknown tool '{name}'"
    try:
        return handler(**arguments)
    except Exception as e:
        return f"Error executing {name}: {e}"


def _project_root() -> Path:
    """Return the effective project root (repo root + project dir)."""
    if config.PROJECT_DIR:
        return Path(config.REPO_ROOT) / config.PROJECT_DIR
    return Path(config.REPO_ROOT)


def _read_file(path: str) -> str:
    # Try project-relative first, then repo-relative
    full_path = _project_root() / path
    if not full_path.exists():
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
    root = _project_root()
    matches = sorted(
        str(p.relative_to(root)) for p in root.glob(pattern) if p.is_file()
    )
    if not matches:
        return f"No files matching pattern: {pattern}"
    if len(matches) > 100:
        return (
            "\n".join(matches[:100])
            + f"\n... ({len(matches)} total, showing first 100)"
        )
    return "\n".join(matches)


def _grep(pattern: str, path: str = ".") -> str:
    search_path = _project_root() / path
    if not search_path.exists():
        return f"Error: Path not found: {path}"
    try:
        result = subprocess.run(
            [
                "grep",
                "-rn",
                "--include=*.js",
                "--include=*.ts",
                "--include=*.go",
                "--include=*.py",
                "--include=*.md",
                "--include=*.json",
                "--include=*.yaml",
                "--include=*.yml",
                pattern,
                str(search_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout.strip()
        if not output:
            return f"No matches found for pattern: {pattern}"
        output = output.replace(str(_project_root()) + "/", "")
        lines = output.split("\n")
        if len(lines) > 50:
            return (
                "\n".join(lines[:50])
                + f"\n... ({len(lines)} total matches, showing first 50)"
            )
        return output
    except subprocess.TimeoutExpired:
        return "Error: grep timed out after 30 seconds"


def _run_command(command: str) -> str:
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
            cwd=str(_project_root()),
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
    full_path = _project_root() / path
    try:
        full_path.resolve().relative_to(Path(config.REPO_ROOT).resolve())
    except ValueError:
        return f"Error: Cannot write outside repository: {path}"
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")

    result = f"File created: {path} ({len(content)} bytes)"

    if path.endswith(".js"):
        validation = _validate_k6_script(path=path)
        result += f"\n\nAuto-validation:\n{validation}"

    return result


def _create_mr_note(body: str) -> str:
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output_path = Path(config.OUTPUT_DIR) / f"mr-note-{timestamp}.md"
    output_path.write_text(body, encoding="utf-8")
    print("\n" + "=" * 60)
    print("  MR NOTE (simulated)")
    print("=" * 60)
    print(body)
    print("=" * 60 + "\n")
    return f"MR note posted successfully. Saved to: {output_path.relative_to(Path(config.REPO_ROOT))}"


def _list_mr_diffs() -> str:
    if "diff" in _mr_context:
        return _mr_context["diff"]
    return "Error: No MR diff available. Use --branch or --sample to provide one."


def _get_mr() -> str:
    if _mr_context:
        import json

        safe = {k: v for k, v in _mr_context.items() if k != "diff"}
        return json.dumps(safe, indent=2)
    return "Error: No MR context available."


def _generate_k6_from_openapi(spec_path: str = "") -> str:
    if not spec_path:
        return "Error: spec_path is required. Use find_files to locate the OpenAPI spec first."
    full_path = _project_root() / spec_path
    if not full_path.exists():
        full_path = Path(config.REPO_ROOT) / spec_path
    if not full_path.exists():
        return f"Error: OpenAPI spec not found at {spec_path}"

    try:
        result = subprocess.run(
            [
                "npx",
                "--yes",
                "@openapitools/openapi-generator-cli",
                "generate",
                "-i",
                str(full_path),
                "-g",
                "k6",
                "-o",
                str(Path(config.OUTPUT_DIR) / "openapi-k6"),
                "--skip-validate-spec",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=config.REPO_ROOT,
        )
        output_script = Path(config.OUTPUT_DIR) / "openapi-k6" / "script.js"
        if output_script.exists():
            content = output_script.read_text()
            return f"Generated k6 skeleton from OpenAPI spec:\n\n{content}"
        return f"Generator ran but no script produced.\nstdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
    except FileNotFoundError:
        return "Error: npx not found. Install Node.js to use OpenAPI generator."
    except subprocess.TimeoutExpired:
        return "Error: OpenAPI generator timed out after 60 seconds"


def _validate_k6_script(path: str) -> str:
    full_path = _project_root() / path
    if not full_path.exists():
        full_path = Path(config.REPO_ROOT) / path
    if not full_path.exists():
        return f"Error: Script not found: {path}"

    issues = []
    content = full_path.read_text(encoding="utf-8")

    try:
        result = subprocess.run(
            ["k6", "inspect", str(full_path)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=config.REPO_ROOT,
        )
        if result.returncode != 0:
            issues.append(f"k6 inspect FAILED: {result.stderr.strip()}")
        else:
            issues.append("k6 inspect: PASSED (valid syntax)")
    except FileNotFoundError:
        issues.append("k6 inspect: SKIPPED (k6 not installed)")

    required_patterns = [
        (r"import\s+http\s+from\s+['\"]k6/http['\"]", "Missing k6/http import"),
        (r"export\s+(?:const|let)\s+options", "Missing options export"),
        (r"export\s+default\s+function", "Missing default function"),
        ("check(", "Missing check() assertions"),
        ("handleSummary", "Missing handleSummary() for structured output"),
    ]
    for pattern, message in required_patterns:
        if "(" in pattern and "\\" not in pattern:
            found = pattern in content
        else:
            found = bool(re.search(pattern, content))
        if not found:
            issues.append(f"LINT: {message}")

    recommended = {
        "thresholds": "No thresholds defined",
        "tags:": "No request tags for filtering",
        "group(": "No group() for logical organization",
        "sleep(": "No sleep() between iterations (may overload target)",
    }
    for pattern, message in recommended.items():
        if pattern not in content:
            issues.append(f"WARN: {message}")

    if "scenarios" not in content:
        issues.append("WARN: No scenarios defined (using default executor)")

    if "errorRate" not in content and "errors" not in content:
        issues.append("WARN: No custom error tracking metric")

    return "\n".join(issues)
