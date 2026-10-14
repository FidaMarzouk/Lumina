"""Immutable collection runs: data/raw/<source>/<run_id>/ + manifest.json."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def git_sha(root: Path) -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return None


def new_run_dir(base: Path, source: str) -> tuple[str, Path]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = base / source / run_id
    d.mkdir(parents=True, exist_ok=False)
    return run_id, d


def write_manifest(run_dir: Path, manifest: dict) -> None:
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                           encoding="utf-8", newline="\n")
