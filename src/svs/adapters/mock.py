from __future__ import annotations

import json
import time
from pathlib import Path

from svs.adapters.base import AgentAdapter
from svs.harness import HarnessConfig, default_fixed_harness, mock_should_apply_repair
from svs.models import AgentRunResult, TaskSpec

# Deterministic per-task fixes applied by mock (golden patches ship with tasks).
_GOLDEN_NAME = "golden_fix.json"


class MockAdapter(AgentAdapter):
    name = "mock"

    def __init__(self, mode: str = "solo") -> None:
        self.mode = mode

    def run(
        self,
        workspace: Path,
        task: TaskSpec,
        *,
        timeout: int = 600,
        harness: HarnessConfig | None = None,
    ) -> AgentRunResult:
        harness = harness or default_fixed_harness()
        start = time.perf_counter()
        golden_path = task.starter_dir.parent / _GOLDEN_NAME
        transcript_parts: list[str] = []
        transcript_parts.append(f"[mock-harness] revision={harness.revision} tools={harness.tools}")

        if self.mode == "swarm":
            transcript_parts.append("[mock-swarm] planner decomposed task into implement+verify")
            time.sleep(0.02)
            transcript_parts.append("[mock-swarm] delegated implement subtask to mock-worker")
            time.sleep(0.02)

        if not mock_should_apply_repair(task, harness):
            duration = time.perf_counter() - start
            transcript_parts.append("[mock-harness] repair withheld — harness policy")
            return AgentRunResult(
                completed=True,
                duration_sec=duration,
                input_tokens=200,
                output_tokens=50,
                cost_usd=self.estimate_cost(200, 50),
                transcript="\n".join(transcript_parts),
                extra={"mode": self.mode, "deterministic": True, "withheld_repair": True},
            )

        if not golden_path.is_file():
            duration = time.perf_counter() - start
            return AgentRunResult(
                completed=False,
                duration_sec=duration,
                error=f"Missing golden fix: {golden_path}",
            )

        spec = json.loads(golden_path.read_text(encoding="utf-8"))
        for rel_path, content in spec.get("files", {}).items():
            target = workspace / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            transcript_parts.append(f"[mock] wrote {rel_path}")

        base_in = 800 + len(task.id) * 17
        base_out = 400 + len(task.prompt) // 4
        if self.mode == "swarm":
            base_in = int(base_in * 1.85)
            base_out = int(base_out * 1.6)
            time.sleep(0.03)

        duration = time.perf_counter() - start
        return AgentRunResult(
            completed=True,
            duration_sec=duration,
            input_tokens=base_in,
            output_tokens=base_out,
            cost_usd=self.estimate_cost(base_in, base_out),
            transcript="\n".join(transcript_parts),
            extra={"mode": self.mode, "deterministic": True},
        )
