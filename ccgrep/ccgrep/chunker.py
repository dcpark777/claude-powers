"""chunker.py — message stream → episodes (the retrieval unit).

Episode = one real user prompt through everything until the next real user
prompt. Sidechain messages fold into the containing episode (errors bubble
up; their offsets remain inside the episode's line range so `show` can
descend). Giant episodes split at retry boundaries: the same error string
recurring starts a new sub-chunk sharing the parent id.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .parser import Msg, SessionMeta

# An episode with more tool calls than this is eligible for retry-splitting.
SPLIT_TOOLCALL_THRESHOLD = 25
_ERR_SIG_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|FAILED|Failed)")


@dataclass
class Episode:
    id: str                     # "<session_id>#<seq>" or "<session_id>#<seq>.<sub>"
    session_id: str
    repo: str
    branch: str
    ts_start: str
    ts_end: str
    start_line: int
    end_line: int
    prompt: str = ""
    prose: str = ""
    errors: str = ""            # newline-joined extracted error strings
    identifiers: str = ""       # split code symbols + file paths
    tools_summary: str = ""     # "Bash command=pytest ..." one-liners
    n_tool_calls: int = 0
    n_errors: int = 0
    had_sidechain: bool = False
    clean_finish: bool = False  # last tool result in the episode was non-error
    outcome: str = "unknown"    # stamped later by outcome.py
    seen_count: int = 1         # stamped later by dedup.py


_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def split_identifier(token: str) -> list[str]:
    """getSnowflakeConn -> [get, snowflake, conn]; snake_case via \\W split."""
    parts = re.split(r"[_\W]+", token)
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        out.extend(s.lower() for s in _CAMEL_RE.split(p) if s)
    return out


def _identifiers_from(texts: list[str]) -> str:
    seen: dict[str, None] = {}
    for t in texts:
        for tok in _IDENT_RE.findall(t)[:400]:
            for part in split_identifier(tok):
                if len(part) > 2:
                    seen.setdefault(part)
            seen.setdefault(tok.lower())
    return " ".join(list(seen)[:600])


def _err_signature(err: str) -> str:
    m = _ERR_SIG_RE.search(err)
    return m.group(0) if m else err[:80]


def _finalize(ep: Episode, prose: list[str], errs: list[str],
              tools: list[str], ident_src: list[str]) -> Episode:
    ep.prose = "\n".join(prose)
    ep.errors = "\n".join(errs)
    ep.tools_summary = " ".join(tools)
    ep.identifiers = _identifiers_from(ident_src + errs + tools)
    ep.n_errors = len(errs)
    return ep


def chunk_session(meta: SessionMeta, msgs: list[Msg]) -> list[Episode]:
    episodes: list[Episode] = []
    seq = -1
    cur: Episode | None = None
    prose: list[str] = []
    errs: list[str] = []
    tools: list[str] = []
    ident_src: list[str] = []
    err_sigs_seen: set[str] = set()
    sub = 0

    def close():
        nonlocal cur
        if cur is not None:
            episodes.append(_finalize(cur, prose, errs, tools, ident_src))
            cur = None

    def open_episode(m: Msg, sub_of: int | None = None):
        nonlocal cur, sub, err_sigs_seen
        prose.clear(); errs.clear(); tools.clear(); ident_src.clear()
        if sub_of is None:
            eid = f"{meta.session_id}#{seq}"
            err_sigs_seen = set()
            subid = 0
        else:
            eid = f"{meta.session_id}#{seq}.{sub_of}"
            subid = sub_of
        sub = subid
        cur = Episode(
            id=eid, session_id=meta.session_id, repo=meta.repo,
            branch=meta.branch, ts_start=m.ts or "", ts_end=m.ts or "",
            start_line=m.line_no, end_line=m.line_no,
        )

    for m in msgs:
        is_prompt = (m.role == "user" and not m.is_sidechain and not m.is_meta
                     and bool(m.text.strip()) and not m.tool_result_errors)
        # tool_result-only user messages continue the current episode.
        has_content = bool(m.text.strip() or m.tool_calls or m.tool_result_errors)
        if is_prompt:
            close()
            seq += 1
            open_episode(m)
            cur.prompt = m.text.strip()
        elif cur is None:
            if not has_content:
                continue
            # session starts mid-flight (resumed): synthetic promptless episode
            seq += 1
            open_episode(m)

        # -- accumulate into current episode --
        cur.end_line = m.line_no
        if m.ts:
            cur.ts_end = m.ts
        if m.is_sidechain:
            cur.had_sidechain = True
        if m.role == "assistant" and m.text and not m.is_sidechain:
            prose.append(m.text)
        if m.ask_user_question:
            prose.append(m.ask_user_question)
        for tc in m.tool_calls:
            cur.n_tool_calls += 1
            tools.append(f"{tc.name} {tc.input_summary}".strip())
        if m.tool_result_errors:
            cur.clean_finish = False
        elif m.tool_results_ok:
            cur.clean_finish = True
        new_retry = False
        for err in m.tool_result_errors:
            errs.append(err)  # sidechain errors bubble up: no sidechain filter here
            sig = _err_signature(err)
            if sig in err_sigs_seen and cur.n_tool_calls > SPLIT_TOOLCALL_THRESHOLD:
                new_retry = True
            err_sigs_seen.add(sig)
        if m.text and m.role == "user" and not is_prompt and not m.is_meta:
            ident_src.append(m.text)

        # retry-boundary split for giant debugging episodes
        if new_retry:
            prompt_keep, ts0 = cur.prompt, cur.ts_start
            close()
            open_episode(m, sub_of=sub + 1)
            cur.prompt = prompt_keep      # sub-chunks inherit the prompt
            cur.ts_start = m.ts or ts0

    close()
    return episodes
