from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from svs.models import TaskSpec

_BUILTIN_ROOT = Path(__file__).resolve().parent / "data" / "builtin"


def default_builtin_suite() -> Path:
    return _BUILTIN_ROOT


def load_suite(suite: str | Path) -> list[TaskSpec]:
    """Load tasks from a directory of task folders or a JSONL manifest."""
    path = Path(suite)
    if not path.is_absolute():
        candidate = Path.cwd() / path
        if candidate.exists():
            path = candidate
        elif (_BUILTIN_ROOT / path.name).exists():
            path = _BUILTIN_ROOT / path.name
        elif path.name == "builtin" and _BUILTIN_ROOT.exists():
            path = _BUILTIN_ROOT

    if path.suffix == ".jsonl":
        return load_swebench_jsonl(path)

    if not path.is_dir():
        raise FileNotFoundError(f"Task suite not found: {suite}")

    tasks: list[TaskSpec] = []
    for entry in sorted(path.iterdir()):
        if not entry.is_dir():
            continue
        manifest = entry / "task.json"
        if not manifest.is_file():
            continue
        tasks.append(_load_task_dir(entry))
    if not tasks:
        raise ValueError(f"No tasks found under {path}")
    return tasks


def _load_task_dir(task_dir: Path) -> TaskSpec:
    raw = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    starter = task_dir / raw.get("starter", "starter")
    hidden = task_dir / raw.get("hidden_tests", "hidden_tests")
    if not starter.is_dir():
        raise ValueError(f"Missing starter dir for {task_dir.name}")
    if not hidden.is_dir():
        raise ValueError(f"Missing hidden_tests for {task_dir.name}")
    return TaskSpec(
        id=raw["id"],
        title=raw.get("title", raw["id"]),
        prompt=raw["prompt"],
        starter_dir=starter.resolve(),
        hidden_tests_dir=hidden.resolve(),
        metadata=raw.get("metadata", {}),
    )


def load_swebench_jsonl(
    jsonl_path: Path,
    *,
    cache_dir: Path | None = None,
    limit: int | None = None,
) -> list[TaskSpec]:
    """
    Load SWE-bench-Lite-style JSONL records into TaskSpec objects.

    Each line should include at least: instance_id, problem_statement.
    Optional: repo, base_commit, patch (not applied — for external harnesses).
    """
    path = Path(jsonl_path)
    tasks: list[TaskSpec] = []
    cache_root = cache_dir or (path.parent / ".svs_swebench_cache")
    cache_root.mkdir(parents=True, exist_ok=True)

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            task = _swebench_record_to_task(record, cache_root)
            tasks.append(task)
            if limit is not None and len(tasks) >= limit:
                break
    return tasks


def _swebench_record_to_task(record: dict, cache_root: Path) -> TaskSpec:
    instance_id = record["instance_id"]
    task_dir = cache_root / instance_id
    starter = task_dir / "starter"
    hidden = task_dir / "hidden_tests"
    if not starter.is_dir():
        starter.mkdir(parents=True)
        readme = starter / "README.md"
        readme.write_text(
            f"# {instance_id}\n\n{record.get('problem_statement', '')}\n",
            encoding="utf-8",
        )
        (starter / "INSTRUCTIONS.txt").write_text(
            record.get("problem_statement", ""),
            encoding="utf-8",
        )
    if not hidden.is_dir():
        hidden.mkdir(parents=True)
        (hidden / "test_placeholder.py").write_text(
            "def test_swebench_requires_external_repo():\n"
            '    """SWE-bench instances need repo checkout; skipped in svs stub."""\n'
            "    import pytest\n"
            "    pytest.skip('SWE-bench repo harness not bundled')\n",
            encoding="utf-8",
        )
    prompt = record.get("problem_statement") or record.get("text") or instance_id
    return TaskSpec(
        id=instance_id,
        title=record.get("title", instance_id),
        prompt=prompt,
        starter_dir=starter.resolve(),
        hidden_tests_dir=hidden.resolve(),
        metadata={
            "source": "swebench-jsonl",
            "repo": record.get("repo"),
            "base_commit": record.get("base_commit"),
        },
    )


def filter_tasks(tasks: Iterable[TaskSpec], task_ids: list[str] | None) -> list[TaskSpec]:
    if not task_ids:
        return list(tasks)
    wanted = set(task_ids)
    selected = [t for t in tasks if t.id in wanted]
    missing = wanted - {t.id for t in selected}
    if missing:
        raise ValueError(f"Unknown task ids: {', '.join(sorted(missing))}")
    return selected
