# ASSUMPTIONS.md — verify against real session files before trusting the index

Every format assumption lives in `ccgrep/parser.py` (tagged `# ASSUMPTION:`)
and `ccgrep/discover.py`. The synthetic fixtures in `tests/fixtures/` encode
the same assumptions — they prove the pipeline, not the format.

Work-machine verification = Phase 0 of START_HERE.md. Several of these were
already confirmed during the Cosmo Phase 0 probe (marked ✓cosmo); re-verify
only the unmarked ones.

| # | Assumption | Where | Status |
|---|------------|-------|--------|
| A1 | Sessions live at `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl` | discover.py | ✓cosmo |
| A2 | Conversation entries have `type: "user"\|"assistant"` with a `message` dict | parser.py | ✓cosmo (encoding scheme confirmed) |
| A3 | `message.content` is a string OR a list of typed blocks (`text`, `tool_use`, `tool_result`, `thinking`) | parser.py | verify |
| A4 | Subagent entries carry `isSidechain: true` | parser.py | ✓cosmo |
| A5 | User-directed questions arrive as `tool_use` named `AskUserQuestion` with `input.questions[0].question` | parser.py | ✓cosmo |
| A6 | `tool_result` blocks may carry `is_error`; content is string or text-block list | parser.py | verify |
| A7 | Session-level fields (`cwd`, `gitBranch`, `sessionId`, `timestamp`, `uuid`) repeat on entries | parser.py | verify |
| A8 | Slash commands / hook output arrive as user messages wrapped in `<command-...>` / `<local-command...>` tags | parser.py (`_is_meta_text`) | verify |
| A9 | Live sessions can have a torn (partially written) final line | parser.py (tolerant reads) | assumed safe either way |
| A10 | `sqlite3` in work Python is compiled with FTS5 | store.py | verify (one-liner: `python -c "import sqlite3; sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE t USING fts5(x)')"`) |
| A11 | `textual` installs from Artifactory | pyproject | verify |
| A12 | Bedrock guardrail tolerates the skill's "project history" phrasing (not self-referential) | skill/SKILL.md | verify in first agent use |

## Verification procedure (Phase 0)

1. Pick 3 real sessions: one plain, one with a subagent, one with a slash
   command. Run: `python -m tests.inspect_real <path>` — it prints which
   assumptions each file confirms/violates (script to be written on the work
   machine if needed; `parse_session` + a pprint is enough).
2. Any violated assumption → fix parser.py ONLY, rerun `pytest`. Downstream
   modules must not change.
3. Replace/augment `tests/fixtures/` with 2-3 sanitized real snippets
   (strip anything sensitive) so the suite tests reality, not assumptions.
