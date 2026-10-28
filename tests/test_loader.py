from pathlib import Path

from svs.tasks.loader import default_builtin_suite, load_suite


def test_builtin_suite_loads_ten_tasks():
    tasks = load_suite(default_builtin_suite())
    assert len(tasks) == 10
    assert {t.id for t in tasks} >= {"fix_add", "fix_fizzbuzz", "fix_binary_search"}


def test_load_suite_by_name_builtin():
    tasks = load_suite("builtin")
    assert len(tasks) >= 8


def test_swebench_jsonl_loader(tmp_path: Path):
    jsonl = tmp_path / "lite.jsonl"
    jsonl.write_text(
        '{"instance_id":"django__django-1","problem_statement":"Fix the bug"}\n',
        encoding="utf-8",
    )
    tasks = load_suite(jsonl)
    assert len(tasks) == 1
    assert tasks[0].id == "django__django-1"
    assert tasks[0].metadata["source"] == "swebench-jsonl"
