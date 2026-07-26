# lens probe — RUNBOOK

Goal: settle four facts about what Claude Code session JSONL records around
edit approvals, **before** the lens SPEC hardens. One evening, read-only,
stdlib-only. Q1 is the design-changing one — Cosmo Phase 0 found
prompt-pending is silent on disk; if edit-pending is silent too, the LIVE
amber card (exact hunk pre-approval) is impossible from passive JSONL.

## Setup

- Work machine, any repo you can scribble in (a throwaway fixture repo is fine).
- Terminal A: `claude` interactive session in the fixture repo.
- Terminal B: `python3 lens_probe.py watch ~/.claude/projects/<this-project-dir>`
  (dir form auto-picks the newest .jsonl and follows rotation).
- Keep default permission mode — you WANT to be asked for approval.

## Scripted session (Terminal A)

Act A — approve:
  prompt: "add a comment line at the top of README.md"
  → when asked, WAIT ~10s staring at Terminal B, then approve.

Act B — deny:
  prompt: "delete the last line of README.md"
  → when asked, deny with an explicit reason typed as your next message
    ("no, I want to keep that line").

Act C — deny then revise:
  prompt: "add a retry helper function to util.py"
  → deny the first proposal with a steering reason
    ("use a decorator instead"), then approve the second proposal.

Act D — payload shapes:
  prompt: "create a new file notes.md with two lines, then change both
  lines using a single multi-edit"
  → approve everything. (Covers Write and MultiEdit payloads.)

Then exit the CC session and run:
  `python3 lens_probe.py inspect <that-session.jsonl>` (Terminal B).

## Checks

| ID | What | How you'll know | Feeds |
|----|------|------------------|-------|
| CHECK_pending_visible | Q1: pending Edit tool_use on disk pre-approval | During Act A's 10s stare: does `[tool_use Edit]` print in watch BEFORE you approve? | LIVE face design |
| CHECK_full_strings | Q4: complete old/new strings in payloads | inspect summary: N/N reconstructable | symbol attribution, diffs |
| CHECK_denial_shape | Q2: what a deny leaves on disk | inspect prints denial-looking results verbatim; also note Act B in watch | rejected state detection |
| CHECK_interrupt_vs_deny | Q2b: deny distinguishable from Esc-interrupt | Optional Act E: interrupt mid-proposal once; compare records | rejected-state honesty |
| CHECK_revision_link | Q3: superseded↔replacement linkage | inspect: compare Act C's two tool_use records for shared ids; else same-file+overlap heuristic | revised state |
| CHECK_no_result | Denied edits: result block vs nothing | inspect flags "NONE ON RECORD" rows | edit-fate state machine |
| CHECK_latency_ts | Timestamps allow proposal→decision delta | inspect latencies ≈ your remembered waits (esp. Act A's 10s) | approval latency feature |
| CHECK_usage | Per-message usage dicts present | inspect summary count > 0 | cost rollup |
| CHECK_rejection_reason | Your deny reason retrievable as next user message | grep Act B's reason string in the JSONL | rejection-reasons feature |

## FINDINGS.md template

    CHECK_pending_visible: VISIBLE / SILENT   (+ how long before approval it appeared)
    CHECK_full_strings:    PASS / list gaps by tool (Edit/Write/MultiEdit)
    CHECK_denial_shape:    verbatim denial result content pasted here
    CHECK_interrupt_vs_deny: DISTINGUISHABLE / IDENTICAL / not run
    CHECK_revision_link:   FIELD <name> / HEURISTIC ONLY
    CHECK_no_result:       denied edits leave: result / nothing / other
    CHECK_latency_ts:      PASS / FAIL
    CHECK_usage:           PASS / FAIL
    CHECK_rejection_reason: PASS / FAIL
    surprises:

## Decision rules

- **Q1 VISIBLE** → LIVE face as mocked (amber card with exact hunk). Spec §LIVE unchanged.
- **Q1 SILENT** → LIVE degrades to applied-ledger + "something pending" banner
  (CHECK_ME-style heuristic, same as Cosmo); the amber hunk card moves to the
  v-later parking lot behind a hook/PTY decision lens does NOT take in v1.
  SESSION face is unaffected either way.
- **Q4 gaps** → any tool without full payloads gets file-level rows only
  (degrade-don't-guess applies to reconstruction too).
- **Q2 denial indistinguishable from interrupt** → merge both into a single
  "not applied" fate in v1; "rejected" as a distinct state waits for evidence.
- **Q3 no linkage field** → revised = heuristic (same file + overlapping
  old_string within one episode), and the spec must label it as heuristic.
- **Latency or usage FAIL** → drop that feature from the crop, no substitutes.

## Notes

- Watch mode only reports NEW events (it seeks to end-of-file); history is
  inspect's job.
- The probe never writes. Bedrock guardrail: prompts above are phrased as
  ordinary file tasks, nothing meta about Claude itself.
