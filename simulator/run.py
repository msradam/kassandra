"""
Kassandra Simulator — Agentic loop for local testing.

Replicates the GitLab Duo Agent Platform agentic loop locally,
using either a local MLX model (OpenAI-compatible) or the Anthropic API.

Usage:
    uv run python -m simulator.run --sample 01-add-batch-endpoint
    uv run python -m simulator.run --sample 01-add-batch-endpoint --anthropic
    uv run python -m simulator.run --sample 01-add-batch-endpoint --dry-run
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .tools import TOOLS, ANTHROPIC_TOOLS, execute_tool


def load_system_prompt() -> str:
    """Load the system prompt from prompts/kassandra-system.md."""
    path = Path(config.SYSTEM_PROMPT_PATH)
    if not path.exists():
        print(f"Error: System prompt not found at {path}")
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def load_sample(sample_name: str) -> str:
    """Load a sample MR context and diff, combining them into a user message."""
    samples_dir = Path(config.SAMPLES_DIR)

    # Find matching files
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
        print(f"Available: {[f.stem for f in (samples_dir / 'mr-contexts').glob('*.json')]}")
        sys.exit(1)

    mr_context = json.loads(context_file.read_text())
    diff_content = diff_file.read_text() if diff_file else "(no diff available)"

    user_message = f"""A merge request has been opened and needs performance testing.

**Merge Request Details:**
- IID: !{mr_context['iid']}
- Title: {mr_context['title']}
- Description: {mr_context['description']}
- Source Branch: {mr_context['source_branch']}
- Target Branch: {mr_context['target_branch']}

**Review Environment URL:** {config.REVIEW_ENV_URL}

**MR Diff:**
```diff
{diff_content}
```

Please analyze this merge request, generate appropriate k6 performance tests, execute them, and post a performance report as an MR note."""

    return user_message


def call_openai(messages: list, verbose: bool = False) -> dict:
    """Call local MLX model via OpenAI-compatible API."""
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
        # Fallback: try without tools (some MLX models don't support function calling)
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
    """Call Anthropic API."""
    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package required. Run: uv pip install anthropic")
        sys.exit(1)

    client = anthropic.Anthropic()

    # Convert messages from OpenAI format to Anthropic format
    anthropic_messages = []
    for msg in messages:
        if msg["role"] == "system":
            continue  # system prompt passed separately
        if msg["role"] == "tool":
            # Anthropic uses tool_result content blocks
            for result in msg.get("tool_results", []):
                anthropic_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": result["tool_use_id"],
                            "content": result["output"],
                        }
                    ],
                })
            continue
        anthropic_messages.append(msg)

    response = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=4096,
        system=system_prompt,
        tools=ANTHROPIC_TOOLS,
        messages=anthropic_messages,
    )
    return response


def extract_tool_calls_openai(response) -> list:
    """Extract tool calls from OpenAI-format response."""
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
    # Fallback: parse tool calls from text content
    content = choice.message.content or ""
    return parse_tool_calls_from_text(content)


def extract_tool_calls_anthropic(response) -> list:
    """Extract tool calls from Anthropic-format response."""
    calls = []
    for block in response.content:
        if block.type == "tool_use":
            calls.append({
                "id": block.id,
                "name": block.name,
                "arguments": block.input,
            })
    return calls


def parse_tool_calls_from_text(text: str) -> list:
    """Fallback parser for models that emit tool calls as text/JSON."""
    calls = []
    # Pattern 1: JSON blocks with tool/name/arguments
    json_pattern = r'\{[^{}]*"(?:tool|name)":\s*"(\w+)"[^{}]*"(?:args|arguments|input)":\s*(\{[^{}]*\})[^{}]*\}'
    for match in re.finditer(json_pattern, text):
        try:
            name = match.group(1)
            args = json.loads(match.group(2))
            calls.append({"id": f"text-{len(calls)}", "name": name, "arguments": args})
        except (json.JSONDecodeError, IndexError):
            continue

    # Pattern 2: function-call-like syntax
    func_pattern = r'(\w+)\((.*?)\)'
    if not calls:
        for match in re.finditer(func_pattern, text):
            name = match.group(1)
            if name in {"read_file", "find_files", "grep", "run_command", "create_file", "create_mr_note"}:
                try:
                    args_str = match.group(2)
                    args = json.loads(args_str) if args_str.startswith("{") else {"path": args_str.strip("'\"")}
                    calls.append({"id": f"text-{len(calls)}", "name": name, "arguments": args})
                except (json.JSONDecodeError, ValueError):
                    continue

    return calls


def build_openai_assistant_message(response) -> dict:
    """Build an assistant message from OpenAI response."""
    choice = response.choices[0]
    msg = {"role": "assistant"}
    if choice.message.content:
        msg["content"] = choice.message.content
    if choice.message.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in choice.message.tool_calls
        ]
    return msg


def build_openai_tool_results(tool_calls: list, results: list) -> dict:
    """Build tool result messages for OpenAI format."""
    messages = []
    for tc, result in zip(tool_calls, results):
        messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": result,
        })
    return messages


def run_kassandra(
    sample_name: str,
    use_anthropic: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
):
    """Main agentic loop."""
    system_prompt = load_system_prompt()
    user_message = load_sample(sample_name)

    if dry_run:
        # In dry-run mode, block k6 execution
        original_execute = execute_tool.__wrapped__ if hasattr(execute_tool, "__wrapped__") else None

    print(f"\n{'=' * 60}")
    print(f"  Kassandra Simulator")
    print(f"  Sample: {sample_name}")
    print(f"  Backend: {'Anthropic' if use_anthropic else 'Local MLX'}")
    print(f"  Dry run: {dry_run}")
    print(f"{'=' * 60}\n")

    # Initialize conversation
    if use_anthropic:
        messages = [{"role": "user", "content": user_message}]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

    # Session log
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    log_path = Path(config.OUTPUT_DIR) / f"session-{timestamp}.log"

    def log(text: str):
        with open(log_path, "a") as f:
            f.write(text + "\n")
        if verbose:
            print(text)

    log(f"Session started: {timestamp}")
    log(f"Sample: {sample_name}")
    log(f"Backend: {'Anthropic' if use_anthropic else 'Local MLX'}")

    for round_num in range(1, config.MAX_TOOL_ROUNDS + 1):
        print(f"\n--- Round {round_num}/{config.MAX_TOOL_ROUNDS} ---")
        log(f"\n--- Round {round_num} ---")

        # Call model
        try:
            if use_anthropic:
                response = call_anthropic(messages, system_prompt, verbose)
                tool_calls = extract_tool_calls_anthropic(response)

                # Get text content
                text_content = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text_content += block.text

                if text_content:
                    log(f"Assistant: {text_content[:500]}")
                    print(f"  [ASSISTANT] {text_content[:200]}...")

                # Build anthropic assistant message
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

        # No tool calls = done
        if not tool_calls:
            print("\n  [DONE] No more tool calls — agent finished.")
            log("Agent finished (no tool calls)")
            break

        # Execute tool calls
        results = []
        for tc in tool_calls:
            name = tc["name"]
            args = tc["arguments"]
            args_preview = json.dumps(args)[:100]
            print(f"  [TOOL] {name}: {args_preview}")
            log(f"Tool call: {name}({json.dumps(args)})")

            # Dry-run: skip k6 execution
            if dry_run and name == "run_command" and "k6 run" in args.get("command", ""):
                result = "(dry-run: k6 execution skipped)"
                print(f"  [DRY-RUN] Skipped k6 execution")
            else:
                result = execute_tool(name, args)

            result_preview = result[:200] if result else "(empty)"
            log(f"Tool result: {result_preview}")
            if verbose:
                print(f"  [RESULT] {result_preview}")
            results.append(result)

        # Append tool results
        if use_anthropic:
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tc["id"],
                        "content": result,
                    }
                    for tc, result in zip(tool_calls, results)
                ],
            })
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
    parser.add_argument(
        "--sample",
        default="01-add-batch-endpoint",
        help="Sample name (without extension)",
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

    run_kassandra(
        sample_name=args.sample,
        use_anthropic=args.anthropic,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
