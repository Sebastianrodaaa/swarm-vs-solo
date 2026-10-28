from __future__ import annotations

from pathlib import Path

from svs.adapters._cli_runner import run_subprocess_agent
from svs.adapters.base import AgentAdapter
from svs.models import AgentRunResult, TaskSpec


class GrokCliAdapter(AgentAdapter):
    name = "grok"

    def run(self, workspace: Path, task: TaskSpec, *, timeout: int = 600) -> AgentRunResult:
        command = ["grok", "agent", "--no-leader", "stdio"]
        # grok reads prompt from stdin in stdio mode
        result = run_subprocess_agent(
            command=command + [task.prompt],
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
