#!/usr/bin/env python3
"""lens_probe — verify what Claude Code session JSONL records about edit approvals.

Answers four design-changing questions for lens (see RUNBOOK.md):
  Q1 pending visibility : does a pending Edit tool_use hit disk BEFORE approval?
  Q2 denial shape       : what does a denied edit's tool_result look like?
  Q3 revision linkage   : can a superseded proposal be tied to its replacement?
  Q4 reconstruction     : do Edit/Write payloads carry full old/new strings?

Stdlib only. Read-only. Never writes anything anywhere.

Usage:
  lens_probe.py watch <session.jsonl | project-dir>     # run DURING the scripted session
  lens_probe.py inspect <session.jsonl>                 # run AFTER the session
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
DENIAL_HINTS = (
    "rejected", "denied", "doesn't want", "does not want",
    "user chose not", "declined", "interrupted",
)


# ── shared parsing ───────────────────────────────────────────────────

def iter_blocks(record):
    """Yield content blocks from one JSONL record, schema-tolerantly."""
    msg = record.get("message")
    if not isinstance(msg, dict):
        return
    content = msg.get("content")
    if isinstance(content, str):
        return
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                yield block


def record_ts(record):
    """Best-effort ISO timestamp from a record; returns (str, epoch|None)."""
    ts = record.get("timestamp") or record.get("ts")
    if not isinstance(ts, str):
        return ("?", None)
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (ts, dt.timestamp())
    except ValueError:
        return (ts, None)


def newest_jsonl(path):
    if os.path.isfile(path):
        return path
    best, best_m = None, -1.0
    for root, _dirs, files in os.walk(path):
        for f in files:
            if f.endswith(".jsonl"):
                p = os.path.join(root, f)
                try:
                    m = os.path.getmtime(p)
                except OSError:
                    continue
                if m > best_m:
                    best, best_m = p, m
    return best


def summarize_input(inp):
    """Compact description of an edit tool_use input dict."""
    if not isinstance(inp, dict):
        return "input=?"
    parts = []
    fp = inp.get("file_path") or inp.get("notebook_path")
    if fp:
        parts.append(fp)
    for key in ("old_string", "new_string", "content"):
        v = inp.get(key)
        if isinstance(v, str):
            parts.append(f"{key}={len(v)}ch")
    edits = inp.get("edits")
    if isinstance(edits, list):
        ok = sum(
            1 for e in edits
            if isinstance(e, dict)
            and isinstance(e.get("old_string"), str)
            and isinstance(e.get("new_string"), str)
        )
        parts.append(f"edits={len(edits)} ({ok} with full old/new)")
    return " ".join(parts) if parts else "input keys: " + ",".join(inp.keys())


# ── watch mode (Q1 lives here) ───────────────────────────────────────

def watch(path):
    target = newest_jsonl(path)
    if not target:
        print(f"no .jsonl found under {path}", file=sys.stderr)
        return 1
    print(f"# watching {target}")
    print("# wall-clock arrival on the left. THE Q1 OBSERVATION:")
    print("# note whether [tool_use Edit ...] prints while CC is still ASKING for approval.")
    print("# Ctrl-C to stop.\n")

    pending = {}          # tool_use_id -> (name, arrival_epoch)
    fh = open(target, "r", encoding="utf-8", errors="replace")
    fh.seek(0, os.SEEK_END)  # only new events; run inspect for history

    try:
        while True:
            line = fh.readline()
            if not line:
                # session files can rotate; re-check newest
                latest = newest_jsonl(path)
                if latest and latest != target:
                    fh.close()
                    target = latest
                    fh = open(target, "r", encoding="utf-8", errors="replace")
                    print(f"\n# switched to {target}\n")
                else:
                    time.sleep(0.25)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                emit("unparseable line")
                continue
            handle_watch_record(rec, pending)
    except KeyboardInterrupt:
        print("\n# stopped.")
        if pending:
            print("# still unresolved at stop (candidates for 'pending was on disk'):")
            for tid, (name, _) in pending.items():
                print(f"#   {name} {tid}")
        return 0
    finally:
        fh.close()


def emit(text):
    now = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
    print(f"{now}  {text}", flush=True)


def handle_watch_record(rec, pending):
    ts, _ = record_ts(rec)
    for block in iter_blocks(rec):
        btype = block.get("type")
        if btype == "tool_use":
            name = block.get("name", "?")
            tid = block.get("id", "?")
            if name in EDIT_TOOLS:
                pending[tid] = (name, time.time())
                emit(f"[tool_use {name}] id={tid} ts={ts} {summarize_input(block.get('input'))}")
                emit("  ^^ IF CC IS STILL WAITING FOR YOUR APPROVAL RIGHT NOW, Q1 = VISIBLE")
            else:
                emit(f"[tool_use {name}] id={tid}")
        elif btype == "tool_result":
            tid = block.get("tool_use_id", "?")
            waited = ""
            if tid in pending:
                name, t0 = pending.pop(tid)
                waited = f" (resolved {time.time() - t0:.1f}s after arrival, was {name})"
            content = flatten_result(block)
            flag = " DENIAL?" if looks_denied(block, content) else ""
            emit(f"[tool_result] id={tid}{waited}{flag} :: {content[:160]}")
    # non-content record types (summary, compaction, etc.)
    rtype = rec.get("type")
    if rtype and rtype not in ("assistant", "user"):
        emit(f"[{rtype}]")


def flatten_result(block):
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(
            b.get("text", "") for b in c if isinstance(b, dict)
        ).strip()
    return repr(c)[:120]


def looks_denied(block, content_text):
    if block.get("is_error"):
        return True
    low = content_text.lower()
    return any(h in low for h in DENIAL_HINTS)


# ── inspect mode (Q2/Q3/Q4 + latency/usage) ──────────────────────────

def inspect(path):
    if not os.path.isfile(path):
        print(f"not a file: {path}", file=sys.stderr)
        return 1

    records = []
    bad = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1

    uses = {}      # id -> {name, input, ts, epoch}
    results = {}   # tool_use_id -> {content, is_error, ts, epoch}
    usage_count = 0

    for rec in records:
        ts, epoch = record_ts(rec)
        msg = rec.get("message")
        if isinstance(msg, dict) and isinstance(msg.get("usage"), dict):
            usage_count += 1
        for block in iter_blocks(rec):
            if block.get("type") == "tool_use" and block.get("name") in EDIT_TOOLS:
                uses[block.get("id")] = {
                    "name": block.get("name"),
                    "input": block.get("input"),
                    "ts": ts, "epoch": epoch,
                }
            elif block.get("type") == "tool_result":
                results[block.get("tool_use_id")] = {
                    "content": flatten_result(block),
                    "is_error": bool(block.get("is_error")),
                    "ts": ts, "epoch": epoch,
                }

    print(f"# {path}")
    print(f"# records={len(records)} unparseable_lines={bad} "
          f"edit_tool_uses={len(uses)} usage_bearing_msgs={usage_count}\n")

    full_strings = 0
    denials = []
    ordered = sorted(uses.items(), key=lambda kv: kv[1]["epoch"] or 0)

    for i, (tid, u) in enumerate(ordered, 1):
        res = results.get(tid)
        inp = u["input"] if isinstance(u["input"], dict) else {}
        has_full = (
            (isinstance(inp.get("old_string"), str) and isinstance(inp.get("new_string"), str))
            or isinstance(inp.get("content"), str)
            or isinstance(inp.get("edits"), list)
        )
        if has_full:
            full_strings += 1
        latency = "?"
        if res and u["epoch"] and res["epoch"]:
            latency = f"{res['epoch'] - u['epoch']:.1f}s"
        print(f"[{i}] {u['name']} id={tid}")
        print(f"    {summarize_input(inp)}")
        print(f"    full_payload={'YES' if has_full else 'NO'}  ts={u['ts']}  proposal→result={latency}")
        if res is None:
            print("    result: NONE ON RECORD (denied-and-dropped? interrupted? note this)")
        else:
            denied = res["is_error"] or looks_denied({"is_error": res["is_error"]}, res["content"])
            tag = "DENIED?" if denied else "ok"
            if denied:
                denials.append((tid, res["content"][:200]))
            print(f"    result[{tag}] is_error={res['is_error']} :: {res['content'][:160]}")
        print()

    print("# ── findings summary (transcribe into FINDINGS.md) ──")
    print(f"CHECK_full_strings   : {full_strings}/{len(uses)} edit payloads reconstructable "
          f"-> {'PASS' if uses and full_strings == len(uses) else 'REVIEW'}")
    print(f"CHECK_denial_shape   : {len(denials)} denial-looking results; verbatim below")
    for tid, c in denials:
        print(f"    {tid}: {c}")
    print("CHECK_revision_link  : MANUAL — for the Act-C pair, compare the denied and the "
          "re-proposed tool_use above: any shared id/parent field? same file+overlapping "
          "old_string is the fallback heuristic.")
    print("CHECK_latency_ts     : latencies printed per edit above "
          "-> PASS if they match your remembered wait times.")
    print(f"CHECK_usage          : {usage_count} messages carry usage dicts "
          f"-> {'PASS' if usage_count else 'FAIL'}")
    print("CHECK_pending_visible: WATCH-MODE ONLY — cannot be reconstructed post-hoc.")
    return 0


# ── entry ────────────────────────────────────────────────────────────

def main(argv):
    if len(argv) != 3 or argv[1] not in ("watch", "inspect"):
        print(__doc__)
        return 2
    if argv[1] == "watch":
        return watch(argv[2])
    return inspect(argv[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
