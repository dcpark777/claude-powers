"""cli.py — entrypoint. Human door prints readable lines (or launches the
TUI with no args-piped tty); Claude door is --json with caps in render_json.
"""
from __future__ import annotations

import argparse
import sys

from . import render_json, search as search_mod
from .store import Store


def _fmt_hit(i: int, h) -> str:
    mark = {"green": "+", "thrash": "~", "unknown": " "}[h.outcome]
    seen = f" (seen {h.seen_count}x)" if h.seen_count > 1 else ""
    ts = (h.ts_end or "")[:10]
    return (f"{i}. [{mark}] {h.repo} {ts}{seen}  {h.id}\n"
            f"     {h.prompt[:90]}\n"
            f"     > {h.snippet}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ccgrep",
                                 description="search your Claude Code history")
    ap.add_argument("--json", action="store_true", help="machine mode (capped)")
    sub = ap.add_subparsers(dest="cmd")

    sp = sub.add_parser("search", help="search episodes (default command)")
    sp.add_argument("query", nargs="+")
    sp.add_argument("--repo")
    sp.add_argument("--since", type=int, metavar="DAYS")
    sp.add_argument("--green", action="store_true")
    sp.add_argument("--limit", type=int, default=10)

    sh = sub.add_parser("show", help="expand one episode")
    sh.add_argument("id")
    sh.add_argument("--around", type=int)
    sh.add_argument("--lines", type=int, default=40)

    ix = sub.add_parser("index", help="build/refresh the index")
    ix.add_argument("--rebuild", action="store_true")

    sub.add_parser("doctor", help="index stats + environment checks")
    te = sub.add_parser("top-errors", help="recurring error clusters")
    te.add_argument("--limit", type=int, default=10)
    sub.add_parser("recent", help="latest episodes per repo")
    sub.add_parser("tui", help="interactive TUI")

    # bare `ccgrep some words` == search
    argv = list(sys.argv[1:] if argv is None else argv)
    known_cmds = {"search", "show", "index", "doctor", "top-errors", "recent", "tui"}
    positional = [a for a in argv if not a.startswith("-")]
    if positional and positional[0] not in known_cmds:
        argv.insert(argv.index(positional[0]), "search")
    args = ap.parse_args(argv)

    store = Store()

    if args.cmd == "index":
        res = search_mod.index(store, rebuild=args.rebuild)
        print(f"indexed {res['files_indexed']}/{res['files_seen']} files")
        return 0

    if args.cmd == "doctor":
        import sqlite3
        st = store.stats()
        try:
            sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(x)")
            st["fts5"] = "ok"
        except sqlite3.OperationalError:
            st["fts5"] = "MISSING — sqlite built without FTS5"
        import json as _json
        print(_json.dumps(st, indent=2))
        return 0

    if args.cmd == "top-errors":
        search_mod.index(store)
        rows = [r for r in store.all_episodes()
                if r["canonical_id"] == r["id"] and r["seen_count"] > 1
                and (r["errors"] or "").strip()]
        rows.sort(key=lambda r: r["seen_count"], reverse=True)
        for r in rows[:args.limit]:
            first = (r["errors"] or "").splitlines()[0][:100]
            print(f"{r['seen_count']:>3}x  {r['repo'] or '?':<20} {first}  ({r['id']})")
        if not rows:
            print("no recurring error clusters yet")
        return 0

    if args.cmd == "recent":
        search_mod.index(store)
        rows = sorted(store.all_episodes(), key=lambda r: r["ts_end"] or "",
                      reverse=True)[:15]
        for r in rows:
            print(f"{(r['ts_end'] or '')[:16]:<17} {r['repo'] or '?':<18} "
                  f"{(r['prompt'] or '')[:70]}")
        return 0

    if args.cmd == "show":
        lines = search_mod.show(store, args.id, around=args.around,
                                lines=args.lines)
        if args.json:
            print(render_json.render_show(args.id, lines))
        else:
            print("\n".join(lines))
        return 0

    if args.cmd == "tui" or args.cmd is None:
        from .tui.app import run_tui
        run_tui(store)
        return 0

    # search
    query = " ".join(args.query)
    hits = search_mod.search(store, query, repo=args.repo,
                             since_days=args.since, green_only=args.green,
                             limit=args.limit)
    if args.json:
        print(render_json.render_search(hits, query))
    else:
        if not hits:
            print("no matches")
        for i, h in enumerate(hits, 1):
            print(_fmt_hit(i, h))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
