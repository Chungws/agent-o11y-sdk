#!/usr/bin/env python3
"""Fake tool-use agent for SDK validation.

Simulates an agent that:
1. Receives a task
2. Calls an LLM to plan
3. Executes tools
4. Summarizes results

Prompt version controls behavior distribution:
- v1: baseline (moderate latency, some errors)
- v2: "improved" (lower latency, fewer errors, but more tokens)

Usage:
    python examples/fake_tool_agent.py --version v1 --episodes 20
    python examples/fake_tool_agent.py --version v2 --episodes 20
"""

from __future__ import annotations

import argparse
import random
import time

import agent_obs
from agent_obs import ExperimentContext


def simulate_llm_call(version: str) -> dict:
    """Simulate LLM call with version-dependent behavior."""
    if version == "v1":
        latency = random.gauss(0.5, 0.15)
        input_tokens = random.randint(200, 400)
        output_tokens = random.randint(50, 150)
        error_rate = 0.1
    else:  # v2
        latency = random.gauss(0.3, 0.1)
        input_tokens = random.randint(300, 600)  # more tokens (longer prompt)
        output_tokens = random.randint(80, 200)
        error_rate = 0.03

    time.sleep(max(0.01, latency))

    if random.random() < error_rate:
        raise TimeoutError("LLM call timed out")

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "plan": ["search", "compute", "format"],
    }


def simulate_tool_call(tool_name: str, version: str) -> str:
    """Simulate tool execution."""
    if version == "v1":
        latency = random.gauss(0.2, 0.08)
        error_rate = 0.05
    else:
        latency = random.gauss(0.15, 0.05)
        error_rate = 0.02

    time.sleep(max(0.01, latency))

    if random.random() < error_rate:
        raise RuntimeError(f"Tool '{tool_name}' failed")

    return f"{tool_name}: done"


def run_episode(run: agent_obs.Run, episode_num: int, version: str) -> None:
    """Run a single episode of the fake agent."""
    with run.episode(f"task-{episode_num}") as ep:
        # Step 1: LLM planning
        try:
            with ep.step("llm_call", name="plan") as step:
                result = simulate_llm_call(version)
                step.record_tokens(
                    input_tokens=result["input_tokens"],
                    output_tokens=result["output_tokens"],
                )
                step.save_artifact("plan.json", result["plan"])
        except TimeoutError:
            return  # episode failed at planning

        # Step 2: Execute tools from plan
        for tool_name in result["plan"]:
            try:
                with ep.step("tool_call", name=f"tool.{tool_name}") as step:
                    output = simulate_tool_call(tool_name, version)
                    step.log("tool completed", output=output)
            except RuntimeError:
                continue  # skip failed tool, continue with next

        # Step 3: Summarize
        with ep.step("llm_call", name="summarize") as step:
            time.sleep(random.gauss(0.2, 0.05))
            step.record_tokens(
                input_tokens=random.randint(100, 200),
                output_tokens=random.randint(30, 80),
            )
            quality = random.gauss(0.85 if version == "v1" else 0.92, 0.05)
            step.record_score("quality", min(1.0, max(0.0, quality)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Fake tool-use agent")
    parser.add_argument("--version", required=True, help="Prompt version (v1, v2)")
    parser.add_argument("--episodes", type=int, default=20, help="Number of episodes")
    parser.add_argument("--endpoint", default="http://localhost:4317", help="OTLP endpoint")
    args = parser.parse_args()

    ctx = ExperimentContext(
        run_id=f"run-{args.version}-{int(time.time())}",
        prompt_version=args.version,
        model="fake-gpt-4",
        task_type="tool-use",
    )

    print(f"Starting {args.episodes} episodes with prompt_version={args.version}")

    with agent_obs.init(ctx, otlp_endpoint=args.endpoint) as run:
        for i in range(args.episodes):
            run_episode(run, i, args.version)
            if (i + 1) % 5 == 0:
                print(f"  completed {i + 1}/{args.episodes} episodes")

    print(f"Done. run_id={ctx.run_id}")


if __name__ == "__main__":
    main()
