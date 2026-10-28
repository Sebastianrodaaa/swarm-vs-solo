from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from svs.models import AgentRunResult, TaskSpec


def run_subprocess_agent(
    *,
    command: list[str],
    workspace: Path,
    task: TaskSpec,
    timeout: int,
    provider: str,
) -> AgentRunResult:
    start = time.perf_counter()
    if shutil.which(command[0]) is None:
        return AgentRunResult(
            completed=False,
            duration_sec=time.perf_counter() - start,
            error=f"{provider} CLI not found on PATH: {command[0]}",
        )

    try:
        proc = subprocess.run(
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return AgentRunResult(
            completed=False,
            duration_sec=time.perf_counter() - start,
            error=f"{provider} timed out after {timeout}s",
            transcript=(exc.stdout or "") + (exc.stderr or ""),
        )

    duration = time.perf_counter() - start
    usage = _extract_usage(proc.stdout + "\n" + proc.stderr)
    completed = proc.returncode == 0
    return AgentRunResult(
        completed=completed,
        duration_sec=duration,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        cost_usd=usage.get("cost_usd", 0.0),
        transcript=proc.stdout[-8000:] if proc.stdout else proc.stderr[-8000:],
        error=None if completed else (proc.stderr or proc.stdout or f"exit {proc.returncode}"),
        extra={"provider": provider, "returncode": proc.returncode},
    )


def _extract_usage(text: str) -> dict[str, float | int]:
    """Best-effort token/cost extraction from CLI JSON or AutoSwarm envelopes."""
    usage: dict[str, float | int] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("ok") and "data" in payload:
            payload = payload["data"]
        if not isinstance(payload, dict):
            continue
        for key in ("usage", "token_usage", "metrics"):
            block = payload.get(key)
            if isinstance(block, dict):
                usage.setdefault("input_tokens", int(block.get("input_tokens", block.get("prompt_tokens", 0))))
                usage.setdefault("output_tokens", int(block.get("output_tokens", block.get("completion_tokens", 0))))
                if "cost_usd" in block:
                    usage.setdefault("cost_usd", float(block["cost_usd"]))
        if "input_tokens" in payload:
            usage.setdefault("input_tokens", int(payload["input_tokens"]))
        if "output_tokens" in payload:
            usage.setdefault("output_tokens", int(payload["output_tokens"]))
    return usage
