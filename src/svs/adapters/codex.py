from __future__ import annotations

from pathlib import Path

from svs.adapters._cli_runner import run_subprocess_agent
from svs.adapters.base import AgentAdapter
from svs.harness import HarnessConfig
from svs.models import AgentRunResult, TaskSpec


class CodexAdapter(AgentAdapter):
    name = "codex"

    def run(
        self,
        workspace: Path,
        task: TaskSpec,
        *,
        timeout: int = 600,
        harness: HarnessConfig | None = None,
    ) -> AgentRunResult:
        # Codex app-server is JSON-RPC; benchmark uses one-shot CLI wrapper when available.
        command = ["codex", "exec", "--full-auto", task.prompt]
        result = run_subprocess_agent(
            command=command,
            workspace=workspace,
            task=task,
            timeout=timeout,
            provider=self.name,
        )
        if result.input_tokens or result.output_tokens:
            result.cost_usd = result.cost_usd or self.estimate_cost(
                result.input_tokens, result.output_tokens
            )
        return result
