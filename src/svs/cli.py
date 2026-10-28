from __future__ import annotations

import argparse
import sys
from pathlib import Path

from svs import __version__
from svs.models import Mode
from svs.report import generate_report
from svs.results import default_results_path
from svs.runner import run_suite
from svs.tasks.loader import filter_tasks, load_suite


def _build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="svs",
        description="swarm-vs-solo benchmark harness (solo agent vs AutoSwarm team)",
    )
    root.add_argument("--version", action="version", version=f"svs {__version__}")
    sub = root.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Run tasks under solo or swarm mode")
    run_p.add_argument(
        "--tasks",
        required=True,
        help="Task suite directory (e.g. builtin) or SWE-bench JSONL path",
    )
    run_p.add_argument("--mode", choices=["solo", "swarm"], required=True)
    run_p.add_argument(
        "--agent",
        required=True,
        help="Agent CLI name (mock, claude, codex, grok, cursor)",
    )
    run_p.add_argument(
        "--results",
        type=Path,
        default=None,
        help="JSONL results file (default: ./results/runs.jsonl)",
    )
    run_p.add_argument("--ids", nargs="*", help="Optional subset of task ids")
    run_p.add_argument("--timeout", type=int, default=600, help="Per-task timeout seconds")
    run_p.add_argument("--limit", type=int, default=None, help="Limit tasks (JSONL suites)")

    rep_p = sub.add_parser("report", help="Aggregate JSONL results into markdown + PNG charts")
    rep_p.add_argument(
        "--results",
        type=Path,
        default=None,
        help="JSONL results file (default: ./results/runs.jsonl)",
    )
    rep_p.add_argument(
        "--output",
        type=Path,
        default=Path("results/report"),
        help="Output directory for report.md and charts",
    )

    return root


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "report":
        return _cmd_report(args)
    return 1


def _cmd_run(args: argparse.Namespace) -> int:
    results_path: Path = args.results or default_results_path()
    suite_path = args.tasks
    if suite_path == "builtin":
        from svs.tasks.loader import default_builtin_suite

        suite_path = str(default_builtin_suite())

    path = Path(suite_path)
    if path.suffix == ".jsonl":
        from svs.tasks.loader import load_swebench_jsonl

        tasks = load_swebench_jsonl(path, limit=args.limit)
    else:
        tasks = load_suite(path)
        if args.limit is not None:
            tasks = tasks[: args.limit]

    tasks = filter_tasks(tasks, args.ids)
    mode: Mode = args.mode
    print(f"Running {len(tasks)} task(s) mode={mode} agent={args.agent} -> {results_path}")
    records = run_suite(
        tasks,
        mode=mode,
        agent=args.agent,
        results_path=results_path,
        timeout=args.timeout,
    )
    passed = sum(1 for r in records if r.passed)
    print(f"Done: {passed}/{len(records)} passed")
    return 0 if passed == len(records) else 2


def _cmd_report(args: argparse.Namespace) -> int:
    results_path = args.results or default_results_path()
    if not results_path.is_file():
        print(f"No results at {results_path}", file=sys.stderr)
        return 1
    out = generate_report(results_path, args.output)
    print(f"Wrote {out['markdown']}")
    for chart in out["charts"]:
        print(f"Wrote {chart}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
