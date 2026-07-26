# KICKOFF — operating instructions for the work-machine agent

Scope: START_HERE.md **Phase 0 and Phase 1 only.** Read START_HERE.md,
SPEC.md, ASSUMPTIONS.md before writing any code.

1. `pip install -e .` + pytest (Artifactory). All 14 tests must pass
   before touching anything. Install or FTS5 failure → stop and report.
2. Phase 0: verify assumptions A3, A6, A7, A8 against 3 real sessions
   (plain / subagent / slash command). Report each confirmed/violated
   with a one-line sample per violation.
3. Violations fix `parser.py` ONLY. If a fix wants chunker/store/rank/
   search, stop and flag — parser/chunker/outcome is slated for
   extraction into a shared library (strata), so boundaries stay clean.
4. Add 2-3 sanitized real fixtures (strip tokens, hostnames, internal
   paths, data values). Suite green with them included.
5. Phase 1: `python -m ccgrep.cli index --rebuild`, then `doctor`.
   Report episode counts + index size; print 5 random episodes via
   `show` for human review of chunk boundaries.

Rules: SPEC wins — gaps get asked, not filled. No v2 features. Read-only
against session files, always. `git init` and commit at each green
checkpoint (post-install, post-Phase-0, post-Phase-1) so parser fixes
are auditable as diffs. Stop after Phase 1 and summarize; do not start
the golden set, skill install, or TUI pass.
