from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from svs.results import read_jsonl


@dataclass
class AggregateRow:
    agent: str
    mode: str
    runs: int
    pass_rate: float
    mean_wall_sec: float
    mean_cost_usd: float
    total_cost_usd: float
    harness: str = "fixed"


@dataclass
class HarnessBatchRow:
    harness: str
    batch_index: int
    runs: int
    pass_rate: float
    eval_only: bool


def aggregate(rows: list[dict]) -> list[AggregateRow]:
    buckets: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        harness = row.get("harness", "fixed")
        buckets[(row["agent"], row["mode"], harness)].append(row)

    out: list[AggregateRow] = []
    for (agent, mode, harness), items in sorted(buckets.items()):
        n = len(items)
        passed = sum(1 for i in items if i.get("passed"))
        out.append(
            AggregateRow(
                agent=agent,
                mode=mode,
                harness=harness,
                runs=n,
                pass_rate=passed / n if n else 0.0,
                mean_wall_sec=sum(i.get("wall_duration_sec", 0) for i in items) / n,
                mean_cost_usd=sum(i.get("cost_usd", 0) for i in items) / n,
                total_cost_usd=sum(i.get("cost_usd", 0) for i in items),
            )
        )
    return out


def aggregate_harness_eval(rows: list[dict]) -> list[AggregateRow]:
    """Held-out eval split only — avoids train-set leakage in harness comparisons."""
    eval_rows = [r for r in rows if r.get("split") == "eval" or r.get("metadata", {}).get("split") == "eval"]
    if not eval_rows:
        eval_rows = [r for r in rows if r.get("harness") == "fixed"]
    return aggregate(eval_rows)


def aggregate_by_batch(rows: list[dict], *, eval_only: bool = False) -> list[HarnessBatchRow]:
    filtered = rows
    if eval_only:
        filtered = [
            r
            for r in rows
            if r.get("split") == "eval" or r.get("metadata", {}).get("split") == "eval"
        ]
    buckets: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in filtered:
        harness = row.get("harness", "fixed")
        batch_index = int(row.get("batch_index", 0))
        buckets[(harness, batch_index)].append(row)

    out: list[HarnessBatchRow] = []
    for (harness, batch_index), items in sorted(buckets.items()):
        n = len(items)
        passed = sum(1 for i in items if i.get("passed"))
        out.append(
            HarnessBatchRow(
                harness=harness,
                batch_index=batch_index,
                runs=n,
                pass_rate=passed / n if n else 0.0,
                eval_only=eval_only,
            )
        )
    return out


def harness_revision_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        harness = row.get("harness", "fixed")
        rev = int(row.get("harness_revision", 0))
        counts[harness].add(rev)
    return {h: len(revs) for h, revs in sorted(counts.items())}


def markdown_table(rows: list[AggregateRow], *, mock_label: bool) -> str:
    lines = [
        "# swarm-vs-solo report",
        "",
    ]
    if mock_label:
        lines.extend(
            [
                "> **MOCK example data** — generated from the deterministic `mock` adapter in CI.",
                "> Do not treat these numbers as real agent performance.",
                "",
            ]
        )
    lines.extend(
        [
            "| Agent | Mode | Harness | Runs | Pass rate | Mean wall (s) | Mean cost ($) | Total cost ($) |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row.agent} | {row.mode} | {row.harness} | {row.runs} | {row.pass_rate:.1%} | "
            f"{row.mean_wall_sec:.3f} | {row.mean_cost_usd:.6f} | {row.total_cost_usd:.6f} |"
        )
    lines.append("")
    return "\n".join(lines)


def markdown_harness_section(
    eval_rows: list[AggregateRow],
    batch_rows: list[HarnessBatchRow],
    rev_counts: dict[str, int],
    *,
    mock_label: bool,
) -> str:
    lines = ["## Harness experiment (held-out eval)", ""]
    if mock_label:
        lines.append("> **MOCK** — co-evolve arm uses deterministic train-batch updates only.")
        lines.append("")
    if eval_rows:
        lines.extend(
            [
                "| Agent | Mode | Harness | Eval runs | Pass rate | Mean wall (s) | Mean cost ($) |",
                "| --- | --- | --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for row in eval_rows:
            lines.append(
                f"| {row.agent} | {row.mode} | {row.harness} | {row.runs} | {row.pass_rate:.1%} | "
                f"{row.mean_wall_sec:.3f} | {row.mean_cost_usd:.6f} |"
            )
        lines.append("")
    if rev_counts:
        lines.append("### Harness revisions observed")
        lines.append("")
        for harness, count in rev_counts.items():
            lines.append(f"- `{harness}`: **{count}** revision(s) in results")
        lines.append("")
    if batch_rows:
        lines.extend(
            [
                "### Pass rate by batch (train batches + eval batch index −1)",
                "",
                "| Harness | Batch | Runs | Pass rate |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for row in batch_rows:
            label = "eval" if row.batch_index < 0 else str(row.batch_index)
            lines.append(
                f"| {row.harness} | {label} | {row.runs} | {row.pass_rate:.1%} |"
            )
        lines.append("")
    return "\n".join(lines)


def write_charts(rows: list[AggregateRow], output_dir: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    agents = sorted({r.agent for r in rows})
    modes = ["solo", "swarm"]
    x = range(len(agents))
    width = 0.35

    def _series(metric: str) -> dict[tuple[str, str], float]:
        lookup: dict[tuple[str, str], float] = {}
        for r in rows:
            if r.harness != "fixed":
                continue
            lookup[(r.agent, r.mode)] = getattr(r, metric)
        return lookup

    charts = [
        ("pass_rate", "Pass rate", "pass_rate.png", True),
        ("mean_wall_sec", "Mean wall time (s)", "mean_wall_time.png", False),
        ("mean_cost_usd", "Mean cost (USD)", "mean_cost.png", False),
    ]

    for field, ylabel, filename, is_rate in charts:
        lookup = _series(field)
        solo_vals = [lookup.get((a, "solo"), 0.0) for a in agents]
        swarm_vals = [lookup.get((a, "swarm"), 0.0) for a in agents]

        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.bar([i - width / 2 for i in x], solo_vals, width, label="solo")
        ax.bar([i + width / 2 for i in x], swarm_vals, width, label="swarm")
        ax.set_xticks(list(x))
        ax.set_xticklabels(agents)
        ax.set_ylabel(ylabel)
        ax.set_title(f"Solo vs swarm — {ylabel}")
        ax.legend()
        if is_rate:
            ax.set_ylim(0, 1.05)
        fig.tight_layout()
        path = output_dir / filename
        fig.savefig(path, dpi=144)
        plt.close(fig)
        written.append(path)

    return written


def write_harness_charts(
    raw_rows: list[dict],
    batch_rows: list[HarnessBatchRow],
    rev_counts: dict[str, int],
    eval_agg: list[AggregateRow],
    output_dir: Path,
) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    harness_arms = sorted({r.get("harness", "fixed") for r in raw_rows})
    if len(harness_arms) < 2 and "coevolve" not in harness_arms:
        return written

    # Pass rate by batch per harness arm
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for harness in harness_arms:
        arm_batches = [b for b in batch_rows if b.harness == harness]
        if not arm_batches:
            continue
        xs = [b.batch_index for b in arm_batches]
        ys = [b.pass_rate for b in arm_batches]
        ax.plot(xs, ys, marker="o", label=harness)
    ax.set_xlabel("Batch index (−1 = held-out eval)")
    ax.set_ylabel("Pass rate")
    ax.set_ylim(0, 1.05)
    ax.set_title("Harness arms — pass rate by batch")
    ax.legend()
    fig.tight_layout()
    path = output_dir / "harness_pass_rate_by_batch.png"
    fig.savefig(path, dpi=144)
    plt.close(fig)
    written.append(path)

    # Revision counts
    if rev_counts:
        fig, ax = plt.subplots(figsize=(6, 4))
        labels = list(rev_counts.keys())
        vals = [rev_counts[k] for k in labels]
        ax.bar(labels, vals, color=["#6366f1", "#22c55e"][: len(labels)])
        ax.set_ylabel("Distinct harness revisions")
        ax.set_title("Harness revision count")
        fig.tight_layout()
        path = output_dir / "harness_revision_count.png"
        fig.savefig(path, dpi=144)
        plt.close(fig)
        written.append(path)

    # Eval split cost/time by harness
    if eval_agg:
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        labels = [f"{r.harness}" for r in eval_agg]
        costs = [r.mean_cost_usd for r in eval_agg]
        walls = [r.mean_wall_sec for r in eval_agg]
        axes[0].bar(labels, costs, color="#f59e0b")
        axes[0].set_title("Held-out eval — mean cost")
        axes[0].set_ylabel("USD")
        axes[1].bar(labels, walls, color="#3b82f6")
        axes[1].set_title("Held-out eval — mean wall time")
        axes[1].set_ylabel("seconds")
        fig.suptitle("Harness arms (eval split only)")
        fig.tight_layout()
        path = output_dir / "harness_eval_cost_time.png"
        fig.savefig(path, dpi=144)
        plt.close(fig)
        written.append(path)

    return written


def generate_report(
    results_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    rows_raw = read_jsonl(results_path)
    agg = aggregate(rows_raw)
    mock_label = all(r.get("agent") == "mock" for r in rows_raw) if rows_raw else True
    md = markdown_table(agg, mock_label=mock_label)

    has_harness_experiment = any(r.get("harness") == "coevolve" for r in rows_raw)
    if has_harness_experiment:
        eval_agg = aggregate_harness_eval(rows_raw)
        batch_rows = aggregate_by_batch(rows_raw, eval_only=False)
        rev_counts = harness_revision_counts(rows_raw)
        md += "\n" + markdown_harness_section(
            eval_agg, batch_rows, rev_counts, mock_label=mock_label
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "report.md"
    md_path.write_text(md, encoding="utf-8")
    charts = write_charts(agg, output_dir) if agg else []
    if has_harness_experiment:
        batch_rows = aggregate_by_batch(rows_raw, eval_only=False)
        eval_agg = aggregate_harness_eval(rows_raw)
        charts.extend(
            write_harness_charts(
                rows_raw,
                batch_rows,
                harness_revision_counts(rows_raw),
                eval_agg,
                output_dir,
            )
        )
    return {"markdown": md_path, "charts": charts, "aggregates": agg}
