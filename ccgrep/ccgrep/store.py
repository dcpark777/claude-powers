"""store.py — owns SQLite exclusively. No other module writes SQL.

Two tables:
  episodes      — metadata + offsets (source of truth)
  episodes_fts  — FTS5 external-content table over the searchable fields

Index lives at ~/.ccgrep/index.db (override with CCGREP_DB for tests).
Incremental indexing: files table records mtime; unchanged files skip.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from .chunker import Episode

DEFAULT_DB = Path(os.environ.get("CCGREP_DB", str(Path.home() / ".ccgrep" / "index.db")))

_SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
  path TEXT PRIMARY KEY, mtime REAL NOT NULL, session_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS episodes (
  id TEXT PRIMARY KEY, session_id TEXT NOT NULL, repo TEXT, branch TEXT,
  ts_start TEXT, ts_end TEXT, start_line INTEGER, end_line INTEGER,
  src_path TEXT, outcome TEXT DEFAULT 'unknown', seen_count INTEGER DEFAULT 1,
  canonical_id TEXT, n_tool_calls INTEGER DEFAULT 0, n_errors INTEGER DEFAULT 0,
  prompt TEXT, prose TEXT, errors TEXT, identifiers TEXT, tools_summary TEXT
);
CREATE INDEX IF NOT EXISTS ix_ep_session ON episodes(session_id);
CREATE INDEX IF NOT EXISTS ix_ep_repo ON episodes(repo);
CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
  prompt, errors, prose, identifiers, tools_summary,
  content='episodes', content_rowid='rowid', tokenize='porter unicode61'
);
"""


class Store:
    def __init__(self, db_path: Path | str = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.db_path)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(_SCHEMA)

    # ---- incremental bookkeeping ----
    def file_is_current(self, path: Path) -> bool:
        row = self.con.execute("SELECT mtime FROM files WHERE path=?",
                               (str(path),)).fetchone()
        return row is not None and abs(row["mtime"] - path.stat().st_mtime) < 1e-6

    def replace_session(self, path: Path, session_id: str, episodes: list[Episode]):
        """Idempotent per-file reindex: delete then insert, one transaction."""
        with self.con:
            old = self.con.execute(
                "SELECT rowid FROM episodes WHERE src_path=?", (str(path),)).fetchall()
            for r in old:
                self.con.execute(
                    "INSERT INTO episodes_fts(episodes_fts, rowid, prompt, errors, "
                    "prose, identifiers, tools_summary) "
                    "SELECT 'delete', rowid, prompt, errors, prose, identifiers, "
                    "tools_summary FROM episodes WHERE rowid=?", (r["rowid"],))
            self.con.execute("DELETE FROM episodes WHERE src_path=?", (str(path),))
            for ep in episodes:
                cur = self.con.execute(
                    "INSERT OR REPLACE INTO episodes (id, session_id, repo, branch,"
                    " ts_start, ts_end, start_line, end_line, src_path, outcome,"
                    " seen_count, canonical_id, n_tool_calls, n_errors, prompt,"
                    " prose, errors, identifiers, tools_summary)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ep.id, ep.session_id, ep.repo, ep.branch, ep.ts_start,
                     ep.ts_end, ep.start_line, ep.end_line, str(path), ep.outcome,
                     ep.seen_count, ep.id, ep.n_tool_calls, ep.n_errors,
                     ep.prompt, ep.prose, ep.errors, ep.identifiers,
                     ep.tools_summary))
                self.con.execute(
                    "INSERT INTO episodes_fts(rowid, prompt, errors, prose,"
                    " identifiers, tools_summary) VALUES (?,?,?,?,?,?)",
                    (cur.lastrowid, ep.prompt, ep.errors, ep.prose,
                     ep.identifiers, ep.tools_summary))
            self.con.execute(
                "INSERT OR REPLACE INTO files (path, mtime, session_id) VALUES (?,?,?)",
                (str(path), path.stat().st_mtime, session_id))

    def set_canonical(self, mapping: dict[str, str]):
        with self.con:
            self.con.executemany(
                "UPDATE episodes SET canonical_id=?,"
                " seen_count=CASE WHEN id=? THEN seen_count ELSE 1 END WHERE id=?",
                [(canon, canon, eid) for eid, canon in mapping.items()])
            # write exemplar seen_counts
            counts: dict[str, int] = {}
            for _, canon in mapping.items():
                counts[canon] = counts.get(canon, 0) + 1
            self.con.executemany(
                "UPDATE episodes SET seen_count=? WHERE id=?",
                [(n, canon) for canon, n in counts.items()])

    def all_episodes(self) -> list[sqlite3.Row]:
        return self.con.execute("SELECT * FROM episodes").fetchall()

    def get_episode(self, ep_id: str) -> sqlite3.Row | None:
        return self.con.execute("SELECT * FROM episodes WHERE id=?",
                                (ep_id,)).fetchone()

    def match(self, fts_query: str, limit: int = 50) -> list[sqlite3.Row]:
        """Raw FTS5 match with per-field bm25 weights applied later in rank.py.
        Returns candidate rows joined with per-field bm25() score."""
        sql = (
            "SELECT e.*, bm25(episodes_fts, ?, ?, ?, ?, ?) AS score"
            " FROM episodes_fts f JOIN episodes e ON e.rowid = f.rowid"
            " WHERE episodes_fts MATCH ? AND e.canonical_id = e.id"
            " ORDER BY score LIMIT ?")
        from .rank import FIELD_WEIGHTS  # data, not SQL
        w = FIELD_WEIGHTS
        return self.con.execute(sql, (w["prompt"], w["errors"], w["prose"],
                                      w["identifiers"], w["tools_summary"],
                                      fts_query, limit)).fetchall()

    def stats(self) -> dict:
        q = self.con.execute
        return {
            "db_path": str(self.db_path),
            "files": q("SELECT COUNT(*) c FROM files").fetchone()["c"],
            "episodes": q("SELECT COUNT(*) c FROM episodes").fetchone()["c"],
            "canonical": q("SELECT COUNT(*) c FROM episodes"
                           " WHERE canonical_id=id").fetchone()["c"],
            "repos": [r["repo"] for r in q(
                "SELECT DISTINCT repo FROM episodes ORDER BY repo").fetchall()],
            "db_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
        }
