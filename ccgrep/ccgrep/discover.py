"""discover.py — find session JSONL files.

ASSUMPTION: sessions live at ~/.claude/projects/<encoded-cwd>/<session-id>.jsonl
(confirmed on the work machine during Cosmo Phase 0). Override the root with
CCGREP_SESSIONS_DIR for tests and nonstandard installs.
"""
from __future__ import annotations

import os
from pathlib import Path


def sessions_root() -> Path:
    env = os.environ.get("CCGREP_SESSIONS_DIR")
    if env:
        return Path(env)
    return Path.home() / ".claude" / "projects"


def find_session_files(root: Path | None = None) -> list[Path]:
    root = root or sessions_root()
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*/*.jsonl") if p.is_file())
