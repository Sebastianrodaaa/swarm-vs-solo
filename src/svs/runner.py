from __future__ import annotations

import time
import uuid
from pathlib import Path

from svs.adapters.registry import resolve_adapter
from svs.evaluate import run_hidden_pytest
from svs.models import Mode, RunRecord, TaskSpec
from svs.results import append_jsonl
from svs.worktree import isolated_git_worktree


def run_task(
    task: TaskSpec,
    *,
    mode: Mode,
    agent: str,
    results_path: Path,
    timeout: int = 600,
) -> RunRecord:
    adapter = resolve_adapter(agent, mode)
    run_id = f"{task.id}-{mode}-{uuid.uuid4().hex[:8]}"
    wall_start = time.perf_counter()

    with isolated_git_worktree(task.starter_dir) as workspace:
        agent_result = adapter.run(workspace, task, timeout=timeout)
        eval_outcome = run_hidden_pytest(workspace, task.hidden_tests_dir)
        wall_duration = time.perf_counter() - wall_start

        passed = agent_result.completed and eval_outcome.passed
        error = agent_result.error
        if agent_result.completed and not eval_outcome.passed:
            error = (error or "") + " pytest failed"

        record = RunRecord(
            run_id=run_id,
            task_id=task.id,
            mode=mode,
            agent=agent,
            passed=passed,
            agent_duration_sec=agent_result.duration_sec,
            eval_duration_sec=eval_outcome.duration_sec,
            wall_duration_sec=wall_duration,
            input_tokens=agent_result.input_tokens,
            output_tokens=agent_result.output_tokens,
            cost_usd=agent_result.cost_usd,
            workspace=str(workspace),
            error=error,
            metadata={
                "adapter": adapter.name,
                "eval_stdout_tail": eval_outcome.stdout[-500:],
            },
        )
        append_jsonl(results_path, record)
        return record


def run_suite(
    tasks: list[TaskSpec],
    *,
    mode: Mode,
    agent: str,
    results_path: Path,
    timeout: int = 600,
) -> list[RunRecord]:
    records: list[RunRecord] = []
    for task in tasks:
        records.append(
            run_task(
                task,
                mode=mode,
                agent=agent,
                results_path=results_path,
                timeout=timeout,
            )
        )
    return records
