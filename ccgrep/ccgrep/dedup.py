"""dedup.py — near-duplicate clustering across the whole index.

You've hit the same Snowflake auth error 14 times; search wants the one
canonical fix plus "seen 14x", not 14 hits drowning everything else.

v1 approach: cluster key = dominant error signature (if any) + top prompt
shingles. Jaccard over 3-word shingles of prompt+errors decides membership.
The exemplar is the best-outcome, most-recent episode; others are stored
but marked non-canonical so search returns only exemplars by default.
"""
from __future__ import annotations

import re

from .chunker import Episode

_ERR_SIG_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|FAILED|Failed)")
_WORD_RE = re.compile(r"[a-z0-9]{2,}")
JACCARD_THRESHOLD = 0.6
_OUTCOME_RANK = {"green": 2, "unknown": 1, "thrash": 0}


def _shingles(text: str, k: int = 3) -> set[str]:
    words = _WORD_RE.findall(text.lower())[:200]
    return {" ".join(words[i:i + k]) for i in range(max(0, len(words) - k + 1))}


def _dominant_sig(ep: Episode) -> str:
    counts: dict[str, int] = {}
    for line in ep.errors.splitlines():
        m = _ERR_SIG_RE.search(line)
        if m:
            counts[m.group(0)] = counts.get(m.group(0), 0) + 1
    return max(counts, key=counts.get) if counts else ""


def cluster(episodes: list[Episode]) -> dict[str, str]:
    """Return {episode_id: canonical_episode_id}. Exemplars map to themselves."""
    buckets: dict[str, list[Episode]] = {}
    for ep in episodes:
        buckets.setdefault(_dominant_sig(ep), []).append(ep)

    canon: dict[str, str] = {}
    for sig, eps in buckets.items():
        if not sig:  # no error signature: only exact-ish prompt dupes cluster
            pass
        clusters: list[list[Episode]] = []
        shingle_cache = {ep.id: _shingles(ep.prompt + " " + ep.errors) for ep in eps}
        for ep in eps:
            placed = False
            for cl in clusters:
                a, b = shingle_cache[ep.id], shingle_cache[cl[0].id]
                if a and b:
                    j = len(a & b) / len(a | b)
                    if j >= JACCARD_THRESHOLD:
                        cl.append(ep)
                        placed = True
                        break
            if not placed:
                clusters.append([ep])
        for cl in clusters:
            exemplar = max(cl, key=lambda e: (_OUTCOME_RANK.get(e.outcome, 1),
                                              e.ts_end))
            exemplar.seen_count = len(cl)
            for e in cl:
                canon[e.id] = exemplar.id
    return canon
