# START_HERE — ccgrep work-machine bootstrap

Read order: this file → SPEC.md → ASSUMPTIONS.md. The deterministic core is
already built and tested (14/14) against synthetic fixtures that encode the
format assumptions. Your job here is to verify those assumptions against
real session files, tune ranking on real history, and wire the skill.

Non-negotiable rules (same as mission/cosmo bundles):
- SPEC wins. Gaps → ask Dan, don't fill.
- Format surprises change `parser.py` (and fixtures) ONLY. If a fix wants
  to touch chunker/store/rank, stop and flag it.
- No v2 features (embeddings, watcher, reader integration).

## Phase 0 — verify assumptions (gate for everything)
1. `pip install -e .[dev]` equivalent: `pip install -e . pytest` from
   Artifactory. Run `pytest` — 14/14 must pass before touching anything.
2. Run `python -m ccgrep.cli doctor` — confirms FTS5 (A10).
3. Follow ASSUMPTIONS.md: parse 3 real sessions (plain / subagent / slash
   command), check A3, A6, A7, A8. Fix parser.py only. Add 2-3 sanitized
   real snippets to tests/fixtures/.
   ✅ Accept: pytest green with real-snippet fixtures included.

## Phase 1 — index the real corpus
1. `python -m ccgrep.cli index --rebuild` over the full history.
   ✅ Accept: completes without error; `doctor` shows plausible episode
   counts; index size noted (expect tens of MB).
2. Spot-read 5 random episodes via `show` — chunk boundaries should look
   like coherent moments, not fragments. Misboundaries → chunker bug, flag.

## Phase 2 — golden set + ranking pass
1. Replace tests/golden.json cases with ~20 real known-answer queries
   (half error-paste, half intent-phrased).
2. Run test_golden. Below 0.8 recall@5 → tune rank.py dicts (weights only),
   rerun. Log each change + score.
   ✅ Accept: recall@5 ≥ 0.8 on real queries.

## Phase 3 — the Claude door in anger
1. Install the skill: copy `ccgrep/skill/` → `~/.claude/skills/project-history-search/`.
2. In a scratch repo, manufacture a recurring-error situation and confirm
   the skill triggers, the JSON stays under budget, and Bedrock's guardrail
   accepts the phrasing (A12). If the guardrail balks, adjust SKILL.md
   wording only.
   ✅ Accept: one real task where Claude cites a past fix with provenance.

## Phase 4 — TUI polish + daily driving
1. `ccgrep` bare launches the TUI; verify in Ghostty + VS Code terminal.
2. Drive it for a week. Collect misses into golden.json.
   ✅ Accept: you reach for it unprompted at least twice.

STOP after Phase 4. v1.1 crop (prompts-only search, similar, OSC52 copy-as)
and any reader integration are separate conversations.
