from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _run_git(cwd: Path, *args: str) -> None:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed in {cwd}: {proc.stderr or proc.stdout}"
        )


@contextmanager
def isolated_git_worktree(starter_dir: Path) -> Iterator[Path]:
    """Copy starter into a fresh repo and expose a linked git worktree path."""
    base = Path(tempfile.mkdtemp(prefix="svs-worktree-"))
    repo_dir = base / "repo"
    worktree_dir = base / "run"
    try:
        repo_dir.mkdir(parents=True)
        shutil.copytree(starter_dir, repo_dir, dirs_exist_ok=True)
        _run_git(repo_dir, "init", "-q")
        _run_git(repo_dir, "config", "user.email", "svs@localhost")
        _run_git(repo_dir, "config", "user.name", "swarm-vs-solo")
        _run_git(repo_dir, "add", "-A")
        _run_git(repo_dir, "commit", "-q", "-m", "svs starter snapshot")
        _run_git(repo_dir, "worktree", "add", str(worktree_dir), "HEAD")
        yield worktree_dir
    finally:
        shutil.rmtree(base, ignore_errors=True)
