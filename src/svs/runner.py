from __future__ import annotations

import time
import uuid
from pathlib import Path

from svs.adapters.registry import resolve_adapter
from svs.evaluate import run_hidden_pytest
from svs.harness import (
    HarnessConfig,
    HarnessKind,
    augment_prompt,
    default_coevolve_seed,
    default_fixed_harness,
    save_harness_revision,
    task_split,
    update_harness_from_train_failures,
)
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
    harness: HarnessConfig | None = None,
    harness_kind: HarnessKind = "fixed",
    split: str = "train",
    batch_index: int = 0,
) -> RunRecord:
    harness = harness or default_fixed_harness()
    adapter = resolve_adapter(agent, mode)
    run_id = f"{task.id}-{mode}-{uuid.uuid4().hex[:8]}"
    wall_start = time.perf_counter()

    task_for_agent = TaskSpec(
        id=task.id,
        title=task.title,
        prompt=augment_prompt(task, harness),
        starter_dir=task.starter_dir,
        hidden_tests_dir=task.hidden_tests_dir,
        metadata={**task.metadata, "base_prompt": task.prompt},
    )

    with isolated_git_worktree(task.starter_dir) as workspace:
        agent_result = adapter.run(workspace, task_for_agent, timeout=timeout, harness=harness)
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
            harness=harness_kind,
            harness_revision=harness.revision,
            split=split,  # type: ignore[arg-type]
            batch_index=batch_index,
            metadata={
                "adapter": adapter.name,
                "eval_stdout_tail": eval_outcome.stdout[-500:],
                "split": split,
                "harness_tools": list(harness.tools),
            },
        )
        append_jsonl(results_path, record)
        return record


def _chunk_tasks(tasks: list[TaskSpec], batch_size: int) -> list[list[TaskSpec]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    return [tasks[i : i + batch_size] for i in range(0, len(tasks), batch_size)]


def run_suite(
    tasks: list[TaskSpec],
    *,
    mode: Mode,
    agent: str,
    results_path: Path,
    timeout: int = 600,
    harness_kind: HarnessKind = "fixed",
    batch_size: int = 2,
    run_dir: Path | None = None,
) -> list[RunRecord]:
    if harness_kind == "fixed":
        harness = default_fixed_harness()
        if run_dir:
            save_harness_revision(run_dir, harness)
        records: list[RunRecord] = []
        for task in tasks:
            records.append(
                run_task(
                    task,
                    mode=mode,
                    agent=agent,
                    results_path=results_path,
                    timeout=timeout,
                    harness=harness,
                    harness_kind="fixed",
                    split=task_split(task.id),
                    batch_index=0,
                )
            )
        return records

    # Co-evolving harness: batch train tasks, update harness, then run held-out eval.
    if run_dir is None:
        run_dir = results_path.parent / "runs" / f"coevolve-{uuid.uuid4().hex[:10]}"
    run_dir.mkdir(parents=True, exist_ok=True)

    tasks_by_id = {t.id: t for t in tasks}
    train_tasks = [t for t in tasks if task_split(t.id) == "train"]
    eval_tasks = [t for t in tasks if task_split(t.id) == "eval"]

    harness = default_coevolve_seed()
    save_harness_revision(run_dir, harness)
    records: list[RunRecord] = []

    for batch_index, batch in enumerate(_chunk_tasks(train_tasks, batch_size)):
        batch_records: list[RunRecord] = []
        for task in batch:
            rec = run_task(
                task,
                mode=mode,
                agent=agent,
                results_path=results_path,
                timeout=timeout,
                harness=harness,
                harness_kind="coevolve",
                split="train",
                batch_index=batch_index,
            )
            batch_records.append(rec)
            records.append(rec)

        failures = [r for r in batch_records if not r.passed]
        if failures:
            harness = update_harness_from_train_failures(harness, failures, tasks_by_id)
            save_harness_revision(run_dir, harness)

    for task in eval_tasks:
        records.append(
            run_task(
                task,
                mode=mode,
                agent=agent,
                results_path=results_path,
                timeout=timeout,
                harness=harness,
                harness_kind="coevolve",
                split="eval",
                batch_index=-1,
            )
        )

    return records
