# ccgrep — SPEC v0

Search your Claude Code history. Two doors, one index: a human TUI and a
capped `--json` mode agents can call. Positioning: personal infrastructure /
base hit — not the viral headline bet.

## Laws

1. **Deterministic core.** Indexing and search are lexical and local. No AI
   in the loop; AI is only ever a *caller*.
2. **The parser is the quarantine.** Every CC format assumption lives in
   `parser.py` (and `discover.py`), tagged and mirrored in ASSUMPTIONS.md.
   A format change touches one file.
3. **Caps are structural.** `render_json.py` enforces token budgets at the
   serialization boundary. No upstream code path can over-answer an agent.
4. **Read-only.** ccgrep never writes to session files. Its only artifact is
   `~/.ccgrep/index.db`.
5. **Boosts are data.** Ranking weights live in dicts in `rank.py`; tuning
   never edits SQL or control flow. Reindexing is the expensive mistake to
   design against — intelligence goes in cheap query-time heuristics.

## Retrieval unit: the episode

One real user prompt through everything until the next real user prompt.

- Tool payloads are metadata, never prose. Exception: error strings are
  extracted into a high-boost `errors` field.
- Sidechains fold into the parent episode (errors bubble up; offsets stay
  within the episode range so `show` can descend).
- Giant episodes (>25 tool calls) split at retry boundaries (same error
  signature recurring); sub-chunks share the parent id (`sid#seq.n`) and
  inherit the prompt.
- Outcome stamped per episode: `green | thrash | unknown` — a ranking
  boost, not a verdict. Signals: clean finish after errors, error ratio,
  signature repetition, next-episode reopening.
- Dedup: cluster key = dominant error signature; Jaccard ≥ 0.6 over 3-word
  shingles of prompt+errors. Exemplar = best outcome, then most recent;
  search returns exemplars only, stamped `seen_count`.

## Ranking

BM25 (FTS5, porter tokenizer) with per-field weights — prompt 4.0, errors
4.0 (equal by decision), prose 2.0, identifiers 1.5, tools_summary 0.5 —
then multiplied by: outcome (green 1.25 / thrash 0.8), same-repo 1.3,
recency half-life 45 days with a 0.6 floor, mild log(seen_count) boost.
Error-shaped queries (ALLCAPS tokens, *Error/*Exception suffixes,
tracebacky punctuation, quoted strings) apply a 2x errors-field multiplier
at query time. AND-first with OR fallback on zero hits.

## Storage

SQLite FTS5, single file at `~/.ccgrep/index.db` (env override `CCGREP_DB`;
sessions root override `CCGREP_SESSIONS_DIR`). Incremental by mtime,
refresh-on-search, `index --rebuild` escape hatch. No daemon in v1.

## The Claude door

`ccgrep --json search ...` → schema v1: `{schema, query, note, hits[≤5]}`,
each hit `{id, session_id, repo, ts, outcome, seen_count, prompt, snippet}`.
Budget ~500 tokens (chars/4), enforced by drop-then-shrink.
`ccgrep --json show <id>` → `{schema, id, lines[], truncated?}`, budget ~800.
The bundled skill (`ccgrep/skill/SKILL.md`) triggers only on recurring/
environmental errors, past references, or stuck-after-2 — and phrases the
capability as *project history search* (Bedrock guardrail, Cosmo finding).

## Feature crop (frozen)

open (resume from hit — TUI `o` key prints `claude --resume <sid>`),
top-errors, prompts-only search (v1.1: `--field prompt`), filter flags
(`--repo/--since/--green`), similar (v1.1: FTS more-like-this), copy-as
variants via OSC52 (v1.1), recent, doctor.

## Quality harness

`tests/golden.json` — known-answer queries scored recall@5 by
`tests/test_golden.py`. Ships with fixture-based entries; the work machine
replaces them with ~20 real queries from Dan's history. Every ranking
change runs against it.

## Deferred (v2+)

Embeddings-hybrid retrieval; synonym packs; ccclip-style bookmarks;
reader integration (shared index, jump-to-moment); Historian feed for
mission; watcher daemon.
