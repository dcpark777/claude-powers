"""outcome.py — stamp green/thrash/unknown per episode.

Crude by design: outcome is a *ranking boost*, not a verdict. Session-level
signal is computed once, then per-episode signal refines it.

Heuristics (v1):
  green   — episode's final stretch is error-free AND the episode is not
            error-dominated overall (errors resolved and work proceeded).
  thrash  — error-dominated episode (many errors relative to tool calls)
            or the same error signature recurring 3+ times.
  unknown — everything else (including prose-only episodes).
"""
from __future__ import annotations

import re

from .chunker import Episode

_ERR_SIG_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|FAILED|Failed)")


def _sig_counts(errors: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in errors.splitlines():
        m = _ERR_SIG_RE.search(line)
        if m:
            counts[m.group(0)] = counts.get(m.group(0), 0) + 1
    return counts


def stamp_outcomes(episodes: list[Episode]) -> list[Episode]:
    for i, ep in enumerate(episodes):
        sigs = _sig_counts(ep.errors)
        max_repeat = max(sigs.values()) if sigs else 0
        err_ratio = ep.n_errors / ep.n_tool_calls if ep.n_tool_calls else 0.0

        if ep.n_tool_calls == 0 and not ep.errors:
            ep.outcome = "unknown"
        elif max_repeat >= 3 or (ep.n_tool_calls >= 5 and err_ratio > 0.5):
            ep.outcome = "thrash"
        elif ep.n_errors == 0 and ep.n_tool_calls > 0:
            ep.outcome = "green"
        elif ep.n_errors > 0 and (ep.clean_finish or err_ratio <= 0.25):
            # hit errors but resolved them (clean finish) or pushed through
            ep.outcome = "green"
        else:
            ep.outcome = "unknown"

        # A next episode reopening the same error signature demotes green.
        if ep.outcome == "green" and i + 1 < len(episodes):
            nxt = _sig_counts(episodes[i + 1].errors)
            if sigs and any(s in nxt for s in sigs):
                ep.outcome = "unknown"
    return episodes
