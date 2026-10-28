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


def aggregate(rows: list[dict]) -> list[AggregateRow]:
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in rows:
        buckets[(row["agent"], row["mode"])].append(row)

    out: list[AggregateRow] = []
    for (agent, mode), items in sorted(buckets.items()):
        n = len(items)
        passed = sum(1 for i in items if i.get("passed"))
        out.append(
            AggregateRow(
                agent=agent,
                mode=mode,
                runs=n,
                pass_rate=passed / n if n else 0.0,
                mean_wall_sec=sum(i.get("wall_duration_sec", 0) for i in items) / n,
                mean_cost_usd=sum(i.get("cost_usd", 0) for i in items) / n,
                total_cost_usd=sum(i.get("cost_usd", 0) for i in items),
            )
        )
    return out


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
            "| Agent | Mode | Runs | Pass rate | Mean wall (s) | Mean cost ($) | Total cost ($) |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            f"| {row.agent} | {row.mode} | {row.runs} | {row.pass_rate:.1%} | "
            f"{row.mean_wall_sec:.3f} | {row.mean_cost_usd:.6f} | {row.total_cost_usd:.6f} |"
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


def generate_report(
    results_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    rows_raw = read_jsonl(results_path)
    agg = aggregate(rows_raw)
    mock_label = all(r.get("agent") == "mock" for r in rows_raw) if rows_raw else True
    md = markdown_table(agg, mock_label=mock_label)
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "report.md"
    md_path.write_text(md, encoding="utf-8")
    charts = write_charts(agg, output_dir) if agg else []
    return {"markdown": md_path, "charts": charts, "aggregates": agg}
