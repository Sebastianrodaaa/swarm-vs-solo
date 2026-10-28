from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from svs.models import RunRecord, TaskSpec

HarnessKind = Literal["fixed", "coevolve"]
SplitKind = Literal["train", "eval"]

_DEFAULT_TOOLS = ["read_file", "write_file", "run_shell"]
_DEFAULT_SYSTEM = (
    "You are a coding agent. Edit files in the workspace to satisfy the task. "
    "Prefer minimal, correct fixes."
)
_DEFAULT_RUBRIC = (
    "Pass if hidden pytest succeeds: agent completed without timeout and all tests green."
)


@dataclass
class HarnessConfig:
    """Versioned agent harness: prompt, tools, rubric, and mock policy hooks."""

    revision: int = 0
    system_prompt: str = _DEFAULT_SYSTEM
    tools: list[str] = field(default_factory=lambda: list(_DEFAULT_TOOLS))
    rubric: str = _DEFAULT_RUBRIC
    policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HarnessConfig:
        return cls(
            revision=int(data.get("revision", 0)),
            system_prompt=str(data.get("system_prompt", _DEFAULT_SYSTEM)),
            tools=list(data.get("tools", _DEFAULT_TOOLS)),
            rubric=str(data.get("rubric", _DEFAULT_RUBRIC)),
            policy=dict(data.get("policy", {})),
        )


def default_fixed_harness() -> HarnessConfig:
    """Static harness used for the fixed experiment arm."""
    return HarnessConfig(
        revision=0,
        system_prompt=_DEFAULT_SYSTEM,
        tools=list(_DEFAULT_TOOLS),
        rubric=_DEFAULT_RUBRIC,
        policy={"arm": "fixed", "always_repair": True},
    )


def default_coevolve_seed() -> HarnessConfig:
    """Initial co-evolving harness before any batch updates."""
    return HarnessConfig(
        revision=0,
        system_prompt=_DEFAULT_SYSTEM,
        tools=list(_DEFAULT_TOOLS),
        rubric=_DEFAULT_RUBRIC,
        policy={
            "arm": "coevolve",
            "authorized_repairs": [],
            "filename_hints": [],
        },
    )


def task_split(task_id: str, *, eval_ratio: float = 0.3) -> SplitKind:
    """Deterministic held-out split; stable across runs."""
    digest = hashlib.sha256(task_id.encode("utf-8")).digest()
    bucket = digest[0] / 255.0
    return "eval" if bucket < eval_ratio else "train"


def augment_prompt(task: TaskSpec, harness: HarnessConfig) -> str:
    tools_line = ", ".join(harness.tools)
    return (
        f"{harness.system_prompt}\n\n"
        f"Available tools: {tools_line}\n"
        f"Grading rubric: {harness.rubric}\n\n"
        f"Task:\n{task.prompt}"
    )


def _filename_hints_from_prompt(prompt: str) -> list[str]:
    return sorted(set(re.findall(r"src/[A-Za-z0-9_./-]+\.py", prompt)))


def update_harness_from_train_failures(
    current: HarnessConfig,
    failures: list[RunRecord],
    tasks_by_id: dict[str, TaskSpec],
) -> HarnessConfig:
    """
    Deterministic harness updater driven only by train-split failures.
    Rewrites prompt, tools, rubric, and mock policy for the next batch.
    """
    authorized = list(current.policy.get("authorized_repairs", []))
    hints = list(current.policy.get("filename_hints", []))

    lessons: list[str] = []
    for record in failures:
        if record.metadata.get("split") != "train":
            continue
        tid = record.task_id
        if tid not in authorized:
            authorized.append(tid)
        task = tasks_by_id.get(tid)
        if task:
            for hint in _filename_hints_from_prompt(task.prompt):
                if hint not in hints:
                    hints.append(hint)
            lessons.append(f"- Task {tid} failed: prioritize edits under {', '.join(_filename_hints_from_prompt(task.prompt)) or 'src/'}")

    next_revision = current.revision + 1
    system_prompt = current.system_prompt
    if lessons:
        system_prompt = (
            f"{current.system_prompt.rstrip()}\n\n"
            f"Lessons from prior train batch (revision {next_revision}):\n"
            + "\n".join(lessons)
        )

    tools = list(current.tools)
    if failures and "apply_structured_repair" not in tools:
        tools.append("apply_structured_repair")

    rubric = current.rubric
    if hints:
        rubric = (
            f"{current.rubric} When the task references a file path seen in prior train failures "
            f"({', '.join(hints)}), ensure that module is corrected before finishing."
        )

    generalize = bool(failures) or bool(hints)

    return HarnessConfig(
        revision=next_revision,
        system_prompt=system_prompt,
        tools=tools,
        rubric=rubric,
        policy={
            "arm": "coevolve",
            "authorized_repairs": authorized,
            "filename_hints": hints,
            "generalize_src_repair": generalize,
        },
    )


def save_harness_revision(run_dir: Path, harness: HarnessConfig) -> Path:
    harness_dir = run_dir / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    path = harness_dir / f"rev_{harness.revision:03d}.json"
    path.write_text(json.dumps(harness.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_harness_revision(run_dir: Path, revision: int) -> HarnessConfig:
    path = run_dir / "harness" / f"rev_{revision:03d}.json"
    return HarnessConfig.from_dict(json.loads(path.read_text(encoding="utf-8")))


def mock_should_apply_repair(task: TaskSpec, harness: HarnessConfig) -> bool:
    policy = harness.policy or {}
    if policy.get("always_repair"):
        return True
    if task.id in policy.get("authorized_repairs", []):
        return True
    prompt = str(task.metadata.get("base_prompt") or task.prompt)
    hints = policy.get("filename_hints", [])
    if any(h in prompt for h in hints):
        return True
    if policy.get("generalize_src_repair") and "src/" in prompt:
        return True
    return False
