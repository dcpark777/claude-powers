"""rank.py — boosts expressed as data. Tuning from golden-set results means
editing WEIGHTS dicts, never SQL (store.py) or control flow.
"""
from __future__ import annotations

import datetime as _dt
import math
import re

# Per-field bm25 weights (passed into bm25() by store.match).
# prompt and errors equal by decision; errors gets a 2x query-time multiplier
# when the query is error-shaped (applied via a second match pass boost).
FIELD_WEIGHTS = {
    "prompt": 4.0,
    "errors": 4.0,
    "prose": 2.0,
    "identifiers": 1.5,
    "tools_summary": 0.5,
}

BOOSTS = {
    "outcome": {"green": 1.25, "unknown": 1.0, "thrash": 0.8},
    "same_repo": 1.3,          # applied when --repo/cwd matches
    "recency_half_life_days": 45.0,
    "recency_floor": 0.6,      # old episodes decay to this, never to zero
    "seen_count_log_base": 1.08,  # mild boost for recurring clusters
    "error_query_errors_mult": 2.0,
}

_ERROR_QUERY_RE = re.compile(
    r"([A-Z_]{4,})|"                    # ALLCAPS tokens: SSL, CERTIFICATE_...
    r"(\w+(?:Error|Exception)\b)|"      # exception suffixes
    r"(Traceback)|(errno)|"
    r"(\"[^\"]+\")|('[^']+')"           # quoted strings
)


def is_error_shaped(query: str) -> bool:
    return bool(_ERROR_QUERY_RE.search(query))


def _recency(ts_end: str, now: _dt.datetime) -> float:
    try:
        ts = _dt.datetime.fromisoformat(ts_end.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return 1.0
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=_dt.timezone.utc)
    days = max(0.0, (now - ts).total_seconds() / 86400.0)
    half = BOOSTS["recency_half_life_days"]
    decayed = 0.5 ** (days / half)
    return BOOSTS["recency_floor"] + (1 - BOOSTS["recency_floor"]) * decayed


def final_score(row, query: str, current_repo: str | None,
                now: _dt.datetime | None = None) -> float:
    """row: sqlite Row with bm25 `score` (lower = better in FTS5) + metadata."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    base = -float(row["score"])  # flip: higher = better
    if is_error_shaped(query) and row["errors"]:
        # cheap proxy for the 2x errors-field multiplier: reward rows whose
        # errors field actually contains a query token
        toks = [t for t in re.findall(r"\w{4,}", query)]
        if any(t.lower() in row["errors"].lower() for t in toks):
            base *= BOOSTS["error_query_errors_mult"]
    base *= BOOSTS["outcome"].get(row["outcome"] or "unknown", 1.0)
    if current_repo and row["repo"] == current_repo:
        base *= BOOSTS["same_repo"]
    base *= _recency(row["ts_end"] or "", now)
    base *= 1.0 + math.log(max(1, row["seen_count"]), 10) * (
        BOOSTS["seen_count_log_base"] - 1.0) * 10
    return base
