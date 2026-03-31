from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def update_from_git_checkout() -> int:
    project_root = Path(__file__).resolve().parents[2]
    git_dir = project_root / ".git"
    if not git_dir.exists():
        print("SerialHub is not running from a git checkout. Re-clone and reinstall to update.")
        return 1

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        print("Update aborted because local uncommitted changes were found.")
        print("Commit or stash changes, then run `serialhub update` again.")
        return 1

    try:
        _run(["git", "pull", "--ff-only"], cwd=project_root)
        _run([sys.executable, "-m", "pip", "install", "-e", str(project_root)], cwd=project_root)
    except subprocess.CalledProcessError as exc:
        print(f"Update failed: {exc}")
        return exc.returncode

    print("SerialHub update complete.")
    return 0
