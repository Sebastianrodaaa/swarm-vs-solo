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


def _write_gif_from_png(png_path: Path, gif_path: Path) -> None:
    from PIL import Image

    img = Image.open(png_path).convert("P", palette=Image.ADAPTIVE)
    # Simple 3-frame pulse for demo preview
    frames = [img]
    for _ in range(2):
        frames.append(img.copy())
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=600,
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
    svs = shutil.which("svs") or str(ROOT / ".venv/bin/svs")

    def step(cmd: list[str]) -> None:
        out = _run(cmd, ROOT)
        transcript.append(("i", " ".join(cmd) + "\n"))
        for line in out.splitlines():
            transcript.append(("o", line + "\r\n"))

    step([py, "-m", "pip", "install", "-e", ".", "-q"])
    step(
        [
            svs,
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
            svs,
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
    step([svs, "report", "--results", str(results), "--output", str(report_dir)])

    _write_cast(transcript)
    png = report_dir / "pass_rate.png"
    if png.is_file():
        _write_gif_from_png(png, DEMO / "report-preview.gif")
    print("Wrote demo artifacts under", DEMO)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
