# ccgrep

Search your Claude Code history — one index, two doors.

- **You**: `ccgrep <query>` → interactive TUI (or plain results). Every
  session you've ever run, searchable in milliseconds.
- **Claude**: `ccgrep --json search <query>` → capped, ranked leads from
  past sessions, so your agent stops re-deriving fixes it already found.

Local, deterministic, read-only. SQLite FTS5 under the hood; the only
artifact is `~/.ccgrep/index.db`.

```
pip install -e .
ccgrep index --rebuild     # first index
ccgrep CERTIFICATE_VERIFY_FAILED
ccgrep top-errors          # your recurring pain, ranked
```

See SPEC.md for design, ASSUMPTIONS.md + START_HERE.md for the
work-machine bring-up.
