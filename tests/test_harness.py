from pathlib import Path

from svs.harness import (
    default_coevolve_seed,
    default_fixed_harness,
    mock_should_apply_repair,
    task_split,
    update_harness_from_train_failures,
)
from svs.models import RunRecord
from svs.report import aggregate_by_batch, aggregate_harness_eval, generate_report, harness_revision_counts
from svs.runner import run_suite
from svs.tasks.loader import default_builtin_suite, load_suite


def test_task_split_is_stable():
    assert task_split("fix_add") == task_split("fix_add")
    assert task_split("fix_add") in ("train", "eval")


def test_mock_fixed_harness_always_repairs():
    tasks = load_suite(default_builtin_suite())
    task = tasks[0]
    assert mock_should_apply_repair(task, default_fixed_harness())


def test_coevolve_updater_only_learns_from_train():
    tasks = load_suite(default_builtin_suite())
    by_id = {t.id: t for t in tasks}
    harness = default_coevolve_seed()
    failure = RunRecord(
        run_id="x",
        task_id=tasks[0].id,
        mode="solo",
        agent="mock",
        passed=False,
        agent_duration_sec=0.1,
        eval_duration_sec=0.1,
        wall_duration_sec=0.2,
        input_tokens=1,
        output_tokens=1,
        cost_usd=0.0,
        workspace="/tmp/w",
        metadata={"split": "train"},
    )
    updated = update_harness_from_train_failures(harness, [failure], by_id)
    assert updated.revision == 1
    assert tasks[0].id in updated.policy["authorized_repairs"]
    assert updated.policy["filename_hints"]


def test_mock_coevolve_loop_and_harness_versions(tmp_path: Path):
    results = tmp_path / "runs.jsonl"
    run_dir = tmp_path / "coevolve-run"
    tasks = load_suite(default_builtin_suite())[:6]
    records = run_suite(
        tasks,
        mode="solo",
        agent="mock",
        results_path=results,
        harness_kind="coevolve",
        batch_size=2,
        run_dir=run_dir,
    )
    assert (run_dir / "harness" / "rev_000.json").is_file()
    revisions = sorted((run_dir / "harness").glob("rev_*.json"))
    assert len(revisions) >= 2

    eval_records = [r for r in records if r.split == "eval"]
    assert eval_records
    assert all(r.passed for r in eval_records)

    train_late = [r for r in records if r.split == "train" and r.batch_index > 0]
    if train_late:
        assert any(r.passed for r in train_late)


def test_report_harness_charts(tmp_path: Path):
    results = tmp_path / "runs.jsonl"
    out = tmp_path / "report"
    tasks = load_suite(default_builtin_suite())[:4]
    run_suite(tasks, mode="solo", agent="mock", results_path=results, harness_kind="fixed")
    run_suite(
        tasks,
        mode="solo",
        agent="mock",
        results_path=results,
        harness_kind="coevolve",
        batch_size=2,
        run_dir=tmp_path / "coevolve",
    )
    artifact = generate_report(results, out)
    assert (out / "harness_pass_rate_by_batch.png").is_file()
    assert (out / "harness_revision_count.png").is_file()
    md = artifact["markdown"].read_text(encoding="utf-8")
    assert "Harness experiment" in md
    assert "MOCK" in md
