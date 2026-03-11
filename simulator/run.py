"""
Kassandra Simulator — Agentic loop for local testing.

Replicates the GitLab Duo Agent Platform agentic loop locally,
using either a local MLX model (OpenAI-compatible) or the Anthropic API.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .tools import TOOLS, ANTHROPIC_TOOLS, execute_tool, set_mr_context


def load_system_prompt() -> str:
    path = Path(config.SYSTEM_PROMPT_PATH)
    if not path.exists():
        print(f"Error: System prompt not found at {path}")
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def load_sample(sample_name: str) -> dict:
    samples_dir = Path(config.SAMPLES_DIR)

    context_file = None
    diff_file = None
    for f in (samples_dir / "mr-contexts").glob("*.json"):
        if sample_name in f.stem:
            context_file = f
            break
    for f in (samples_dir / "diffs").glob("*.diff"):
        if sample_name in f.stem:
            diff_file = f
            break

    if not context_file:
        print(f"Error: No MR context found for sample '{sample_name}'")
        print(
            f"Available: {[f.stem for f in (samples_dir / 'mr-contexts').glob('*.json')]}"
        )
        sys.exit(1)

    mr_context = json.loads(context_file.read_text())
    diff_content = diff_file.read_text() if diff_file else "(no diff available)"

    return {
        "iid": mr_context["iid"],
        "title": mr_context["title"],
        "description": mr_context.get("description", ""),
        "source_branch": mr_context.get("source_branch", "feature-branch"),
        "target_branch": mr_context.get("target_branch", "main"),
        "author": mr_context.get("author", "developer"),
        "diff": diff_content,
    }


def load_branch(branch: str) -> dict:
    target = "main"
    try:
        diff = subprocess.run(
            ["git", "diff", f"{target}...{branch}", "--"],
            capture_output=True,
            text=True,
            cwd=config.REPO_ROOT,
        )
        if diff.returncode != 0:
            print(f"Error: git diff failed: {diff.stderr}")
            sys.exit(1)
        diff_content = diff.stdout
        if not diff_content.strip():
            print(f"Error: No diff between {target} and {branch}")
            sys.exit(1)
    except FileNotFoundError:
        print("Error: git not found")
        sys.exit(1)

    log = subprocess.run(
        ["git", "log", f"{target}..{branch}", "--oneline", "-1"],
        capture_output=True,
        text=True,
        cwd=config.REPO_ROOT,
    )
    title = log.stdout.strip().split(" ", 1)[-1] if log.stdout.strip() else branch

    return {
        "iid": 99,
        "title": title,
        "description": f"Branch {branch} changes for performance testing",
        "source_branch": branch,
        "target_branch": target,
        "author": "developer",
        "diff": diff_content,
    }


def build_user_message(mr: dict) -> str:
    return f"""A merge request has been opened and needs performance testing.

**Merge Request Details:**
- IID: !{mr["iid"]}
- Title: {mr["title"]}
- Description: {mr["description"]}
- Source Branch: {mr["source_branch"]}
- Target Branch: {mr["target_branch"]}

**Review Environment URL:** {config.REVIEW_ENV_URL}

Please analyze this merge request, generate appropriate k6 performance tests, execute them, and post a performance report as an MR note.

Note: Use the `list_merge_request_diffs` tool to retrieve the full diff. Use `get_merge_request` for MR metadata. Use `generate_k6_from_openapi` to get a base k6 skeleton from the OpenAPI spec. Use `validate_k6_script` after writing scripts to check for issues."""


def call_openai(messages: list, verbose: bool = False) -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        print("Error: openai package required. Run: uv pip install openai")
        sys.exit(1)

    client = OpenAI(base_url=config.LOCAL_BASE_URL, api_key="not-needed")

    try:
        response = client.chat.completions.create(
            model=config.LOCAL_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=4096,
            temperature=0.3,
        )
        return response
    except Exception as e:
        if verbose:
            print(f"  [WARN] Tool-calling failed ({e}), falling back to text mode")
        response = client.chat.completions.create(
            model=config.LOCAL_MODEL,
            messages=messages,
            max_tokens=4096,
            temperature=0.3,
        )
        return response


def call_anthropic(messages: list, system_prompt: str, verbose: bool = False) -> dict:
    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package required. Run: uv pip install anthropic")
        sys.exit(1)

    client = anthropic.Anthropic(max_retries=5)

    anthropic_messages = []
    for msg in messages:
        if msg["role"] == "system":
            continue
        if msg["role"] == "tool":
            for result in msg.get("tool_results", []):
                anthropic_messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": result["tool_use_id"],
                                "content": result["output"],
                            }
                        ],
                    }
                )
            continue
        anthropic_messages.append(msg)

    # Cache system prompt and tool definitions to avoid re-processing each round
    cached_tools = [*ANTHROPIC_TOOLS]
    cached_tools[-1] = {**cached_tools[-1], "cache_control": {"type": "ephemeral"}}

    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=cached_tools,
        messages=anthropic_messages,
    )

    # Log token usage for cost visibility
    usage = response.usage
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
    if verbose:
        print(
            f"  [TOKENS] in={usage.input_tokens} out={usage.output_tokens} "
            f"cache_read={cache_read} cache_create={cache_create}"
        )

    return response


def extract_tool_calls_openai(response) -> list:
    choice = response.choices[0]
    if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
        return [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": json.loads(tc.function.arguments),
            }
            for tc in choice.message.tool_calls
        ]
    content = choice.message.content or ""
    return parse_tool_calls_from_text(content)


def extract_tool_calls_anthropic(response) -> list:
    calls = []
    for block in response.content:
        if block.type == "tool_use":
            calls.append(
                {
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                }
            )
    return calls


def parse_tool_calls_from_text(text: str) -> list:
    calls = []
    json_pattern = r'\{[^{}]*"(?:tool|name)":\s*"(\w+)"[^{}]*"(?:args|arguments|input)":\s*(\{[^{}]*\})[^{}]*\}'
    for match in re.finditer(json_pattern, text):
        try:
            name = match.group(1)
            args = json.loads(match.group(2))
            calls.append({"id": f"text-{len(calls)}", "name": name, "arguments": args})
        except (json.JSONDecodeError, IndexError):
            continue

    func_pattern = r"(\w+)\((.*?)\)"
    if not calls:
        for match in re.finditer(func_pattern, text):
            name = match.group(1)
            if name in {
                "read_file",
                "find_files",
                "grep",
                "run_command",
                "create_file_with_contents",
                "create_merge_request_note",
            }:
                try:
                    args_str = match.group(2)
                    args = (
                        json.loads(args_str)
                        if args_str.startswith("{")
                        else {"path": args_str.strip("'\"")}
                    )
                    calls.append(
                        {"id": f"text-{len(calls)}", "name": name, "arguments": args}
                    )
                except (json.JSONDecodeError, ValueError):
                    continue

    return calls


def build_openai_assistant_message(response) -> dict:
    choice = response.choices[0]
    msg = {"role": "assistant"}
    if choice.message.content:
        msg["content"] = choice.message.content
    if choice.message.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in choice.message.tool_calls
        ]
    return msg


def build_openai_tool_results(tool_calls: list, results: list) -> list[dict]:
    messages = []
    for tc, result in zip(tool_calls, results):
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            }
        )
    return messages


def run_kassandra(
    mr_context: dict,
    use_anthropic: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
):
    system_prompt = load_system_prompt()
    set_mr_context(mr_context)
    user_message = build_user_message(mr_context)

    source = mr_context.get("source_branch", "unknown")
    print(f"\n{'=' * 60}")
    print("  Kassandra Simulator")
    print(f"  MR: !{mr_context['iid']} — {mr_context['title']}")
    print(f"  Branch: {source}")
    print(f"  Backend: {'Anthropic' if use_anthropic else 'Local MLX'}")
    print(f"  Dry run: {dry_run}")
    print(f"{'=' * 60}\n")

    if use_anthropic:
        messages = [{"role": "user", "content": user_message}]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = Path(config.OUTPUT_DIR) / f"session-{timestamp}.log"

    def log(text: str):
        with open(log_path, "a") as f:
            f.write(text + "\n")
        if verbose:
            print(text)

    log(f"Session started: {timestamp}")
    log(f"MR: !{mr_context['iid']} — {mr_context['title']}")
    log(f"Backend: {'Anthropic' if use_anthropic else 'Local MLX'}")

    for round_num in range(1, config.MAX_TOOL_ROUNDS + 1):
        print(f"\n--- Round {round_num}/{config.MAX_TOOL_ROUNDS} ---")
        log(f"\n--- Round {round_num} ---")

        try:
            if use_anthropic:
                response = call_anthropic(messages, system_prompt, verbose)
                tool_calls = extract_tool_calls_anthropic(response)

                text_content = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text_content += block.text

                if text_content:
                    log(f"Assistant: {text_content[:500]}")
                    print(f"  [ASSISTANT] {text_content[:200]}...")

                messages.append({"role": "assistant", "content": response.content})
            else:
                response = call_openai(messages, verbose)
                tool_calls = extract_tool_calls_openai(response)

                content = response.choices[0].message.content or ""
                if content:
                    log(f"Assistant: {content[:500]}")
                    print(f"  [ASSISTANT] {content[:200]}...")

                messages.append(build_openai_assistant_message(response))
        except Exception as e:
            log(f"Error calling model: {e}")
            print(f"  [ERROR] Model call failed: {e}")
            break

        if not tool_calls:
            print("\n  [DONE] No more tool calls — agent finished.")
            log("Agent finished (no tool calls)")
            break

        results = []
        for tc in tool_calls:
            name = tc["name"]
            args = tc["arguments"]
            args_preview = json.dumps(args)[:100]
            print(f"  [TOOL] {name}: {args_preview}")
            log(f"Tool call: {name}({json.dumps(args)})")

            if (
                dry_run
                and name == "run_command"
                and "k6 run" in args.get("command", "")
            ):
                result = "(dry-run: k6 execution skipped)"
                print("  [DRY-RUN] Skipped k6 execution")
            else:
                result = execute_tool(name, args)

            result_preview = result[:200] if result else "(empty)"
            log(f"Tool result: {result_preview}")
            if verbose:
                print(f"  [RESULT] {result_preview}")
            results.append(result)

        if use_anthropic:
            # Truncate tool results to limit context growth across rounds
            max_result_chars = 8000
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tc["id"],
                            "content": (
                                r
                                if len(r) <= max_result_chars
                                else r[:max_result_chars] + "\n... [truncated]"
                            ),
                        }
                        for tc, r in zip(tool_calls, results)
                    ],
                }
            )
        else:
            for msg in build_openai_tool_results(tool_calls, results):
                messages.append(msg)

    log(f"\nSession ended. Total rounds: {round_num}")
    print(f"\n{'=' * 60}")
    print(f"  Session complete. Log: {log_path.relative_to(Path(config.REPO_ROOT))}")
    print(f"{'=' * 60}\n")

    return messages


def main():
    parser = argparse.ArgumentParser(description="Kassandra Simulator")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--sample",
        help="Sample name from samples/ directory",
    )
    source.add_argument(
        "--branch",
        help="Local git branch to diff against main",
    )
    parser.add_argument(
        "--anthropic",
        action="store_true",
        help="Use Anthropic API instead of local model",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate test scripts but don't execute k6",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed output",
    )
    args = parser.parse_args()

    if args.anthropic:
        os.environ["KASSANDRA_USE_ANTHROPIC"] = "1"

    if args.sample:
        mr_context = load_sample(args.sample)
    else:
        mr_context = load_branch(args.branch)

    run_kassandra(
        mr_context=mr_context,
        use_anthropic=args.anthropic,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
