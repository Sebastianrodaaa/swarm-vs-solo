from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EvalOutcome:
    passed: bool
    duration_sec: float
    stdout: str
    stderr: str


def run_hidden_pytest(workspace: Path, hidden_tests_dir: Path, timeout: int = 120) -> EvalOutcome:
    """Run hidden pytest suite against code in workspace (tests copied to temp dir)."""
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="svs-tests-") as tmp:
        tests_root = Path(tmp) / "tests"
        tests_root.mkdir()
        for item in hidden_tests_dir.iterdir():
            dest = tests_root / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

        pythonpath_parts = [str(workspace)]
        src_dir = workspace / "src"
        if src_dir.is_dir():
            pythonpath_parts.insert(0, str(src_dir))
        env = {"PYTHONPATH": os.pathsep.join(pythonpath_parts)}
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(tests_root),
                "-q",
                "--tb=short",
            ],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **env},
        )
        duration = time.perf_counter() - start
        return EvalOutcome(
            passed=proc.returncode == 0,
            duration_sec=duration,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
