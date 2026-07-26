"""render_json.py — the Claude door.

Token caps are enforced HERE, at the serialization boundary, so no upstream
code can accidentally over-answer an agent. The CLI is incapable of
returning more than TOKEN_BUDGET tokens (approximated as chars/4) in --json
mode; hits are dropped, then snippets truncated, to fit.

Schema is versioned and stable: agents depend on it.
"""
from __future__ import annotations

import json

from .search import Hit

SCHEMA_VERSION = 1
TOKEN_BUDGET_DEFAULT = 500
SHOW_TOKEN_BUDGET_DEFAULT = 800
_CHARS_PER_TOKEN = 4
MAX_HITS_JSON = 5


def _approx_tokens(s: str) -> int:
    return len(s) // _CHARS_PER_TOKEN + 1


def _hit_dict(h: Hit) -> dict:
    return {
        "id": h.id,
        "session_id": h.session_id,
        "repo": h.repo,
        "ts": h.ts_end,
        "outcome": h.outcome,       # green | thrash | unknown
        "seen_count": h.seen_count,
        "prompt": h.prompt,
        "snippet": h.snippet,
    }


def render_search(hits: list[Hit], query: str,
                  token_budget: int = TOKEN_BUDGET_DEFAULT) -> str:
    payload = {
        "schema": SCHEMA_VERSION,
        "query": query,
        "note": ("Results are leads from past sessions, not verified truths. "
                 "Prefer green outcomes and recent timestamps. Expand one hit "
                 "with: ccgrep show <id> --json"),
        "hits": [_hit_dict(h) for h in hits[:MAX_HITS_JSON]],
    }
    out = json.dumps(payload, indent=None)
    # enforcement loop: drop hits, then shrink snippets/prompts
    while _approx_tokens(out) > token_budget and payload["hits"]:
        if len(payload["hits"]) > 3:
            payload["hits"].pop()
        else:
            shrunk = False
            for h in payload["hits"]:
                for k in ("snippet", "prompt"):
                    if len(h[k]) > 60:
                        h[k] = h[k][: max(60, len(h[k]) // 2)]
                        shrunk = True
            if not shrunk:
                payload["hits"].pop()
        out = json.dumps(payload, indent=None)
    return out


def render_show(ep_id: str, lines: list[str],
                token_budget: int = SHOW_TOKEN_BUDGET_DEFAULT) -> str:
    payload = {"schema": SCHEMA_VERSION, "id": ep_id, "lines": lines}
    out = json.dumps(payload, indent=None)
    while _approx_tokens(out) > token_budget and payload["lines"]:
        payload["lines"] = payload["lines"][:-max(1, len(payload["lines"]) // 5)]
        payload["truncated"] = True
        out = json.dumps(payload, indent=None)
    return out
