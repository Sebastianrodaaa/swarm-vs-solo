from pathlib import Path

from svs.worktree import isolated_git_worktree


def test_isolated_git_worktree_creates_git(tmp_path: Path):
    starter = tmp_path / "starter"
    starter.mkdir()
    (starter / "file.txt").write_text("hello", encoding="utf-8")
    with isolated_git_worktree(starter) as wt:
        assert (wt / "file.txt").read_text(encoding="utf-8") == "hello"
        assert (wt / ".git").is_file() or (wt.parent / "repo" / ".git").exists()
