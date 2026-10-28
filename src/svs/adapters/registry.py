from __future__ import annotations

from svs.adapters.autoswarm import AutoSwarmAdapter
from svs.adapters.base import AgentAdapter
from svs.adapters.claude import ClaudeCodeAdapter
from svs.adapters.codex import CodexAdapter
from svs.adapters.cursor_cli import CursorCliAdapter
from svs.adapters.grok import GrokCliAdapter
from svs.adapters.mock import MockAdapter
from svs.models import Mode

SOLO_ADAPTERS: dict[str, type[AgentAdapter]] = {
    "mock": MockAdapter,
    "claude": ClaudeCodeAdapter,
    "codex": CodexAdapter,
    "grok": GrokCliAdapter,
    "cursor": CursorCliAdapter,
}


def resolve_adapter(agent: str, mode: Mode) -> AgentAdapter:
    key = agent.lower()
    if mode == "solo":
        if key not in SOLO_ADAPTERS:
            known = ", ".join(sorted(SOLO_ADAPTERS))
            raise ValueError(f"Unknown agent {agent!r}. Choose from: {known}")
        cls = SOLO_ADAPTERS[key]
        if key == "mock":
            return cls(mode="solo")
        return cls()

    # swarm: AutoSwarm orchestrates the same underlying CLI (mock simulates swarm locally)
    if key == "mock":
        return MockAdapter(mode="swarm")
    if key not in SOLO_ADAPTERS:
        known = ", ".join(sorted(SOLO_ADAPTERS))
        raise ValueError(f"Unknown swarm child agent {agent!r}. Choose from: {known}")
    return AutoSwarmAdapter(child_agent=key, mode="swarm")
