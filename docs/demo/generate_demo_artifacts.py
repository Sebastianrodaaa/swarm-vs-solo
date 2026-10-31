#!/usr/bin/env python3
"""Generate committed demo artifacts (MOCK data) for docs/demo/."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO = Path(__file__).resolve().parent


def _run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    return (proc.stdout + proc.stderr).strip()


def _write_cast(lines: list[tuple[float, str, str]]) -> None:
    cast_path = DEMO / "swarm-vs-solo-mock.cast"
    header = {"version": 2, "width": 100, "height": 26, "timestamp": int(time.time())}
    with cast_path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(header) + "\n")
        t = 0.0
        for kind, text in lines:
            t += 0.4
            handle.write(json.dumps([t, kind, text]) + "\n")


def _write_gif_from_charts(chart_paths: list[Path], gif_path: Path) -> None:
    from PIL import Image, ImageDraw

    frames: list[Image.Image] = []
    target_size = (800, 460)
    for chart in chart_paths:
        if not chart.is_file():
            continue
        base = Image.open(chart).convert("RGBA")
        base.thumbnail((800, 400), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", target_size, (15, 23, 42, 255))
        ox = (target_size[0] - base.width) // 2
        oy = 36 + (400 - base.height) // 2
        canvas.paste(base, (ox, oy), base)
        draw = ImageDraw.Draw(canvas)
        title = chart.stem.replace("_", " ").title()
        draw.text((24, 12), f"MOCK report — {title}", fill=(248, 250, 252))
        draw.text(
            (24, target_size[1] - 28),
            "Deterministic mock adapter · not real agents",
            fill=(148, 163, 184),
        )
        frames.append(canvas.convert("P", palette=Image.ADAPTIVE))

    if not frames:
        return
    hold = frames + frames  # linger on each chart
    hold[0].save(
        gif_path,
        save_all=True,
        append_images=hold[1:],
        duration=1200,
        loop=0,
    )


def main() -> int:
    results = DEMO / "mock-runs.jsonl"
    report_dir = DEMO / "report"
    if results.exists():
        results.unlink()
    if report_dir.exists():
        shutil.rmtree(report_dir)

    transcript: list[tuple[str, str]] = []
    py = sys.executable
    svs_bin = shutil.which("svs")
    svs_prefix = [svs_bin] if svs_bin else [py, "-m", "svs.cli"]

    def step(args: list[str]) -> None:
        cmd = svs_prefix + args
        out = _run(cmd, ROOT)
        transcript.append(("i", " ".join(cmd) + "\n"))
        for line in out.splitlines():
            transcript.append(("o", line + "\r\n"))

    _run([py, "-m", "pip", "install", "-e", ".", "-q"], ROOT)
    step(
        [
            "run",
            "--tasks",
            "builtin",
            "--mode",
            "solo",
            "--agent",
            "mock",
            "--limit",
            "4",
            "--results",
            str(results),
        ]
    )
    step(
        [
            "run",
            "--tasks",
            "builtin",
            "--mode",
            "swarm",
            "--agent",
            "mock",
            "--limit",
            "4",
            "--results",
            str(results),
        ]
    )
    step(
        [
            "run",
            "--tasks",
            "builtin",
            "--mode",
            "solo",
            "--agent",
            "mock",
            "--limit",
            "6",
            "--harness",
            "fixed",
            "--results",
            str(results),
        ]
    )
    step(
        [
            "run",
            "--tasks",
            "builtin",
            "--mode",
            "solo",
            "--agent",
            "mock",
            "--limit",
            "6",
            "--harness",
            "coevolve",
            "--batch-size",
            "2",
            "--run-dir",
            str(DEMO / "coevolve-run"),
            "--results",
            str(results),
        ]
    )
    step(["report", "--results", str(results), "--output", str(report_dir)])

    _write_cast(transcript)
    charts = [
        report_dir / "pass_rate.png",
        report_dir / "mean_wall_time.png",
        report_dir / "mean_cost.png",
        report_dir / "harness_pass_rate_by_batch.png",
        report_dir / "harness_revision_count.png",
        report_dir / "harness_eval_cost_time.png",
    ]
    _write_gif_from_charts(charts, DEMO / "report-preview.gif")
    print("Wrote demo artifacts under", DEMO)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
