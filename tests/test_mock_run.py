from pathlib import Path

from svs.report import aggregate, markdown_table
from svs.results import read_jsonl
from svs.runner import run_suite
from svs.tasks.loader import default_builtin_suite, filter_tasks, load_suite


def test_mock_solo_passes_all_builtin(tmp_path: Path):
    results = tmp_path / "runs.jsonl"
    tasks = filter_tasks(load_suite(default_builtin_suite()), ["fix_add", "fix_subtract"])
    records = run_suite(tasks, mode="solo", agent="mock", results_path=results)
    assert all(r.passed for r in records)
    rows = read_jsonl(results)
    assert len(rows) == 2
    assert rows[0]["mode"] == "solo"


def test_mock_swarm_and_report(tmp_path: Path):
    results = tmp_path / "runs.jsonl"
    tasks = load_suite(default_builtin_suite())[:3]
    run_suite(tasks, mode="solo", agent="mock", results_path=results)
    run_suite(tasks, mode="swarm", agent="mock", results_path=results)
    agg = aggregate(read_jsonl(results))
    md = markdown_table(agg, mock_label=True)
    assert "MOCK example data" in md
    assert any(a.mode == "swarm" for a in agg)
