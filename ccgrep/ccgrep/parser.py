"""parser.py — the format-quarantine zone.

Every assumption about Claude Code's session JSONL format lives HERE and
nowhere else. If Anthropic changes the format, this is the only file that
should need to change. Downstream modules (chunker, outcome, ...) consume
the typed `Msg` stream and never touch raw JSON.

Format assumptions are tagged `# ASSUMPTION:` and mirrored in
ASSUMPTIONS.md for work-machine verification against real session files.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional


@dataclass
class ToolCall:
    name: str
    input_summary: str          # one-line summary of the input, never the payload
    error_text: str = ""        # extracted error text from the matching result
    is_error: bool = False


@dataclass
class Msg:
    role: str                   # "user" | "assistant" | "system" | "other"
    text: str                   # human-authored / prose text only
    line_no: int                # 0-based line offset in the source file
    ts: Optional[str] = None    # ISO timestamp string as found
    uuid: str = ""
    is_sidechain: bool = False
    is_meta: bool = False       # command wrappers, hook output, etc.
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_result_errors: list[str] = field(default_factory=list)
    tool_results_ok: int = 0    # non-error tool results in this message
    ask_user_question: str = "" # AskUserQuestion prompt text, if present


@dataclass
class SessionMeta:
    session_id: str
    repo: str = ""              # derived from cwd
    branch: str = ""
    cwd: str = ""
    path: str = ""


# Fields whose values are payloads we must never index as prose.
_PAYLOAD_INPUT_KEYS = {"content", "file_text", "new_str", "old_str", "new_string",
                       "old_string", "plan", "todos"}
_ERROR_MARKERS = ("error", "Error", "ERROR", "exception", "Exception", "Traceback",
                  "traceback", "FAILED", "failed", "fatal:")
_MAX_ERROR_CHARS = 600
_MAX_INPUT_SUMMARY = 120


def _first_str(*vals) -> str:
    for v in vals:
        if isinstance(v, str) and v:
            return v
    return ""


def _summarize_tool_input(name: str, inp: dict) -> str:
    """One line: the *identifying* argument (path, command, pattern), no payloads."""
    if not isinstance(inp, dict):
        return ""
    for key in ("file_path", "path", "command", "pattern", "query", "url",
                "description", "prompt"):
        v = inp.get(key)
        if isinstance(v, str) and v:
            return f"{key}={v[:_MAX_INPUT_SUMMARY]}"
    keys = [k for k in inp.keys() if k not in _PAYLOAD_INPUT_KEYS]
    return ",".join(keys[:5])


def _extract_error(text: str) -> str:
    """Return error-looking content from a tool result, else ''. Keeps the tail
    (tracebacks put the exception last) capped at _MAX_ERROR_CHARS."""
    if not text:
        return ""
    if any(m in text for m in _ERROR_MARKERS):
        return text[-_MAX_ERROR_CHARS:]
    return ""


def _content_blocks(message: dict):
    # ASSUMPTION: entry["message"]["content"] is either a string or a list of
    # typed blocks ({"type": "text"|"tool_use"|"tool_result"|"thinking", ...}).
    content = message.get("content")
    if isinstance(content, str):
        yield {"type": "text", "text": content}
        return
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                yield block


def _result_text(block: dict) -> str:
    # ASSUMPTION: tool_result content is a string or a list of text blocks.
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for b in c:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(str(b.get("text", "")))
        return "\n".join(parts)
    return ""


def _is_meta_text(text: str) -> bool:
    # ASSUMPTION: slash-command invocations and hook/system wrappers arrive as
    # user messages containing XML-ish tags like <command-name>, <local-command-stdout>.
    t = text.lstrip()
    return t.startswith("<command-") or t.startswith("<local-command") or \
        t.startswith("<system-reminder")


def parse_session(path: str | Path) -> tuple[SessionMeta, list[Msg]]:
    """Parse one session JSONL file into (meta, ordered message list).

    Tolerant by design: unknown line types are skipped, malformed lines are
    skipped, missing fields default. A partially-written last line (live
    session) must never raise.
    """
    path = Path(path)
    meta = SessionMeta(session_id=path.stem, path=str(path))
    msgs: list[Msg] = []

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue  # torn write on a live session
            if not isinstance(entry, dict):
                continue

            # ASSUMPTION: session-level fields (cwd, gitBranch, sessionId)
            # repeat on entries; first occurrence wins.
            if not meta.cwd and isinstance(entry.get("cwd"), str):
                meta.cwd = entry["cwd"]
                meta.repo = Path(meta.cwd).name
            if not meta.branch and isinstance(entry.get("gitBranch"), str):
                meta.branch = entry["gitBranch"]
            if isinstance(entry.get("sessionId"), str):
                meta.session_id = entry["sessionId"]

            etype = entry.get("type")
            # ASSUMPTION: conversation entries have type "user" | "assistant"
            # and carry a "message" dict; other types (summary, system, ...)
            # are not conversation turns.
            if etype not in ("user", "assistant"):
                continue
            message = entry.get("message")
            if not isinstance(message, dict):
                continue

            msg = Msg(
                role=etype,
                text="",
                line_no=line_no,
                ts=entry.get("timestamp"),
                uuid=_first_str(entry.get("uuid")),
                # ASSUMPTION: sidechain (subagent) entries carry isSidechain=true.
                is_sidechain=bool(entry.get("isSidechain", False)),
            )

            texts: list[str] = []
            for block in _content_blocks(message):
                btype = block.get("type")
                if btype == "text":
                    texts.append(str(block.get("text", "")))
                elif btype == "tool_use":
                    name = _first_str(block.get("name"))
                    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
                    # ASSUMPTION: user-directed questions arrive as
                    # tool_use with name "AskUserQuestion" (Cosmo Phase 0 finding).
                    if name == "AskUserQuestion":
                        q = inp.get("questions")
                        if isinstance(q, list) and q and isinstance(q[0], dict):
                            msg.ask_user_question = _first_str(q[0].get("question"))
                        else:
                            msg.ask_user_question = _first_str(inp.get("question"))
                    msg.tool_calls.append(
                        ToolCall(name=name, input_summary=_summarize_tool_input(name, inp)))
                elif btype == "tool_result":
                    err = _extract_error(_result_text(block))
                    is_err = bool(block.get("is_error")) or bool(err)
                    if err:
                        msg.tool_result_errors.append(err)
                    if is_err and msg.tool_calls:
                        msg.tool_calls[-1].is_error = True
                    if not is_err:
                        msg.tool_results_ok += 1
                # "thinking" blocks intentionally not indexed (internal, noisy).

            msg.text = "\n".join(t for t in texts if t)
            if msg.role == "user" and _is_meta_text(msg.text):
                msg.is_meta = True
            msgs.append(msg)

    return meta, msgs


def iter_sessions(paths: list[Path]) -> Iterator[tuple[SessionMeta, list[Msg]]]:
    for p in paths:
        yield parse_session(p)
