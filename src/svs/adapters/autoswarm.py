from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from svs.adapters.base import AgentAdapter
from svs.models import AgentRunResult, TaskSpec


class AutoSwarmAdapter(AgentAdapter):
    """Run a task through AutoSwarm's `autoswarm run` (host delegates to a child CLI)."""

    name = "autoswarm"

    def __init__(self, child_agent: str, mode: str = "swarm") -> None:
        self.child_agent = child_agent
        self.mode = mode

    def run(self, workspace: Path, task: TaskSpec, *, timeout: int = 600) -> AgentRunResult:
        start = time.perf_counter()
        binary = shutil.which("autoswarm")
        if binary is None:
            return AgentRunResult(
                completed=False,
                duration_sec=time.perf_counter() - start,
                error="autoswarm CLI not found; pip install autoswarm or add to PATH",
            )

        swarm_prompt = (
            f"{task.prompt}\n\n"
            "You may delegate implementation to a child agent if helpful, "
            "then verify the workspace passes local checks."
        )
        command = [
            binary,
            "run",
            "--agent",
            self.child_agent,
            "--cwd",
            str(workspace),
            "--no-parent",
            swarm_prompt,
        ]
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
                error=f"autoswarm timed out after {timeout}s",
                transcript=(exc.stdout or "") + (exc.stderr or ""),
            )

        duration = time.perf_counter() - start
        usage = _parse_autoswarm_output(proc.stdout)
        ok = proc.returncode == 0
        err: str | None = None
        if not ok:
            err = proc.stderr or proc.stdout or f"exit {proc.returncode}"
        return AgentRunResult(
            completed=ok,
            duration_sec=duration,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cost_usd=usage.get("cost_usd", 0.0),
            transcript=proc.stdout[-8000:],
            error=err,
            extra={"child_agent": self.child_agent, "mode": self.mode},
        )


def _parse_autoswarm_output(stdout: str) -> dict[str, float | int]:
    usage: dict[str, float | int] = {}
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            envelope = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(envelope, dict):
            continue
        data = envelope.get("data") if envelope.get("ok") else envelope
        if isinstance(data, dict):
            result_path = data.get("result_path") or data.get("directory")
            if isinstance(result_path, str):
                rp = Path(result_path) / "result.json"
                if rp.is_file():
                    try:
                        result = json.loads(rp.read_text(encoding="utf-8"))
                        block = result.get("usage") or result.get("metrics") or {}
                        if isinstance(block, dict):
                            usage["input_tokens"] = int(
                                block.get("input_tokens", block.get("prompt_tokens", 0))
                            )
                            usage["output_tokens"] = int(
                                block.get("output_tokens", block.get("completion_tokens", 0))
                            )
                    except (OSError, json.JSONDecodeError):
                        pass
    return usage
