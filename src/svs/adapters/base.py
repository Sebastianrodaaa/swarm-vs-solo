from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from svs.harness import HarnessConfig
from svs.models import AgentRunResult, TaskSpec


class AgentAdapter(ABC):
    name: str

    @abstractmethod
    def run(
        self,
        workspace: Path,
        task: TaskSpec,
        *,
        timeout: int = 600,
        harness: HarnessConfig | None = None,
    ) -> AgentRunResult:
        """Execute the agent on the task within workspace."""

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Default linear cost model; override per provider."""
        return (input_tokens * 3.0 + output_tokens * 15.0) / 1_000_000.0
