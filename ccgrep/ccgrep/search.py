"""search.py — query → ranked results. Owns indexing orchestration
(refresh-on-search) and query preprocessing.
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass
from pathlib import Path

from . import discover
from .chunker import chunk_session
from .dedup import cluster
from .outcome import stamp_outcomes
from .parser import parse_session
from .rank import final_score
from .store import Store


@dataclass
class Hit:
    id: str
    session_id: str
    repo: str
    ts_end: str
    outcome: str
    seen_count: int
    score: float
    prompt: str
    snippet: str
    src_path: str
    start_line: int
    end_line: int


def index(store: Store, root: Path | None = None, rebuild: bool = False) -> dict:
    """Incremental by mtime; --rebuild reindexes everything."""
    files = discover.find_session_files(root)
    changed = 0
    all_eps = []
    for path in files:
        if not rebuild and store.file_is_current(path):
            continue
        meta, msgs = parse_session(path)
        eps = stamp_outcomes(chunk_session(meta, msgs))
        store.replace_session(path, meta.session_id, eps)
        changed += 1
    # dedup runs across the whole corpus after any change
    if changed:
        rows = store.all_episodes()
        from .chunker import Episode
        eps = [Episode(id=r["id"], session_id=r["session_id"], repo=r["repo"],
                       branch=r["branch"], ts_start=r["ts_start"],
                       ts_end=r["ts_end"], start_line=r["start_line"],
                       end_line=r["end_line"], prompt=r["prompt"] or "",
                       prose=r["prose"] or "", errors=r["errors"] or "",
                       outcome=r["outcome"], n_tool_calls=r["n_tool_calls"],
                       n_errors=r["n_errors"]) for r in rows]
        store.set_canonical(cluster(eps))
    return {"files_seen": len(files), "files_indexed": changed}


_FTS_UNSAFE = re.compile(r"[^\w\s]")


def to_fts_query(query: str) -> str:
    """User text → safe FTS5 query: bare terms OR'd loosely via implicit AND,
    falling back to OR when AND yields nothing (handled by caller)."""
    terms = [t for t in _FTS_UNSAFE.sub(" ", query).split() if t]
    return " ".join(f'"{t}"' for t in terms) if terms else '""'


def _snippet(row, query: str, max_chars: int = 160) -> str:
    """Prefer the field that matched: errors first for error-y content."""
    toks = [t.lower() for t in re.findall(r"\w{3,}", query)]
    for fieldname in ("errors", "prompt", "prose"):
        text = (row[fieldname] or "").strip()
        if not text:
            continue
        low = text.lower()
        for t in toks:
            i = low.find(t)
            if i >= 0:
                start = max(0, i - 40)
                return re.sub(r"\s+", " ", text[start:start + max_chars]).strip()
    return re.sub(r"\s+", " ", (row["prompt"] or row["prose"] or "")[:max_chars]).strip()


def search(store: Store, query: str, repo: str | None = None,
           since_days: int | None = None, green_only: bool = False,
           limit: int = 10, auto_index: bool = True) -> list[Hit]:
    if auto_index:
        index(store)
    fts = to_fts_query(query)
    rows = store.match(fts, limit=100)
    if not rows:  # AND too strict → OR fallback
        terms = fts.split()
        if len(terms) > 1:
            rows = store.match(" OR ".join(terms), limit=100)
    now = _dt.datetime.now(_dt.timezone.utc)
    hits = []
    for r in rows:
        if repo and r["repo"] != repo:
            continue
        if green_only and r["outcome"] != "green":
            continue
        if since_days is not None:
            try:
                ts = _dt.datetime.fromisoformat(
                    (r["ts_end"] or "").replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=_dt.timezone.utc)
                if (now - ts).days > since_days:
                    continue
            except ValueError:
                pass
        hits.append(Hit(
            id=r["id"], session_id=r["session_id"], repo=r["repo"] or "",
            ts_end=r["ts_end"] or "", outcome=r["outcome"] or "unknown",
            seen_count=r["seen_count"], score=final_score(r, query, repo, now),
            prompt=(r["prompt"] or "")[:200], snippet=_snippet(r, query),
            src_path=r["src_path"], start_line=r["start_line"],
            end_line=r["end_line"]))
    hits.sort(key=lambda h: h.score, reverse=True)
    return hits[:limit]


def show(store: Store, ep_id: str, around: int | None = None,
         lines: int = 40) -> list[str]:
    """Return raw transcript lines for an episode (capped), rendered simply.
    `around` = line offset within the source file to center on."""
    row = store.get_episode(ep_id)
    if row is None:
        return [f"episode not found: {ep_id}"]
    path = Path(row["src_path"])
    if not path.exists():
        return [f"source file missing: {path}"]
    meta, msgs = parse_session(path)
    lo, hi = row["start_line"], row["end_line"]
    if around is not None:
        lo, hi = max(lo, around - lines // 2), min(hi, around + lines // 2)
    out = []
    for m in msgs:
        if not (lo <= m.line_no <= hi):
            continue
        tag = "sidechain " if m.is_sidechain else ""
        if m.text.strip():
            out.append(f"[{m.role}{' ' + tag.strip() if tag else ''}] "
                       f"{m.text.strip()[:500]}")
        for tc in m.tool_calls:
            flag = " !err" if tc.is_error else ""
            out.append(f"  [tool{flag}] {tc.name} {tc.input_summary}")
        for err in m.tool_result_errors:
            out.append(f"  [error] {err[:300]}")
        if len(out) >= lines:
            out.append("  ... (capped; raise --lines or open the session)")
            break
    return out
