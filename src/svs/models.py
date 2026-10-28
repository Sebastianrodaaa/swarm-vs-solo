from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


Mode = Literal["solo", "swarm"]


@dataclass(frozen=True)
class TaskSpec:
    id: str
    title: str
    prompt: str
    starter_dir: Path
    hidden_tests_dir: Path
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "prompt": self.prompt,
            "starter_dir": str(self.starter_dir),
            "hidden_tests_dir": str(self.hidden_tests_dir),
            "metadata": self.metadata,
        }


@dataclass
class AgentRunResult:
    """Outcome of an agent invocation (not pytest pass/fail)."""

    completed: bool
    duration_sec: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    transcript: str = ""
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunRecord:
    run_id: str
    task_id: str
    mode: Mode
    agent: str
    passed: bool
    agent_duration_sec: float
    eval_duration_sec: float
    wall_duration_sec: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    workspace: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)
