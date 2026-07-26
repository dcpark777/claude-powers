# MASTER_RUNBOOK.md — strata / lens / reader campaign

**You are Claude, reading this on Dan's work machine.** This document is
your complete instruction set for guiding and executing the remaining
campaign. Read it fully, detect the current stage (§State detection), tell
Dan where things stand, and proceed stage by stage. Dan is the operator;
you do the mechanical work, he does approvals and anything marked OPERATOR.

Sibling files in this bundle (read when their stage arrives, don't
duplicate their content): STRATA.md (library design + laws + layer API),
LENS_RUNBOOK.md (probe details), lens_probe.py (probe tool),
change-lens-mockup.jsx (lens design reference), RUNSHEET.md (human-oriented
summary of this file).

## Ground rules

1. **One active build at a time.** Probes may share an evening; builds may not overlap.
2. **Stop at gates.** Each stage ends with a STOP GATE — summarize results, get Dan's explicit go before the next stage.
3. **Never git push or open PRs without asking** (work-managed settings require approval anyway — don't fight it).
4. **Probes are read-only.** Nothing under ~/.claude/ is ever written to.
5. **Degrade, don't guess.** If reality contradicts this runbook (missing file, changed format), report the discrepancy instead of improvising around it.
6. **Everything strata inherits STRATA.md's 7 laws.** Read that section before Stage 3.

## Current state (as written, July 26 2026)

- ccgrep Phase 0-1: **DONE.** Real-file verification passed with zero
  parser changes (A3/A6/A7/A8 confirmed). Index: 187 parent sessions, 911
  episodes, 782 canonical, 35 repos. 17/17 tests green incl. 3 sanitized
  real fixtures.
- **Deferred finding (Stage 3 fixes it):** real subagents live in separate
  files `<parent-sid>/subagents/agent-<agentId>.jsonl` (entries carry
  isSidechain:true; linked by nesting + sessionId + agentId). ccgrep's
  `*/*.jsonl` discover glob misses them — 86 files, ~24% of sessions
  currently skipped. DO NOT fix inside ccgrep; it's strata's first native
  work item.
- lens probe: NOT run. strata: not extracted. lens: probe stage. reader: spec stage, waits for Stage 5.

## State detection (run on every fresh start)

Check in order; first miss = current stage:

| Evidence | Meaning |
|---|---|
| ~/dev/cc-tools layout exists, ccgrep tests green | Stage 1 done |
| FINDINGS.md exists in _campaign | Stage 2 done |
| strata repo exists with tests green + ccgrep pinned to it | Stage 3 done |
| strata has edits() layer + lens SPEC.md exists | Stage 4a done |
| lens v1 builds/runs | Stage 4 done |
| reader implementation exists | Stage 5 done |

Report detected stage to Dan before doing anything.

---

## STAGE 1 — machine layout (fresh start)

Target structure — one campaign root, docs and repos separated:

```
~/dev/cc-tools/
├── _campaign/          # this bundle's contents + FINDINGS.md; git repo (docs are audit-worthy)
├── ccgrep/             # repo — exists now
├── strata/             # repo — created in Stage 3.1
└── lens/               # repo — created in Stage 4.2
~/tmp/lens-fixture/     # Stage 2 throwaway; deliberately OUTSIDE cc-tools
```

### 1.1 Campaign dir

The campaign dir may be either of:
- **A cloned transfer repo (preferred, Dan's "claude-powers"):** this
  bundle's files committed unzipped at its root, plus ccgrep-project.zip.
  The clone at `~/dev/cc-tools/<repo>` IS the campaign dir — no separate
  git init needed. Campaign artifacts (FINDINGS.md, notes) are committed
  here; pushing is OPERATOR (Dan approves/runs).
- **A plain dir:**

```bash
mkdir -p ~/dev/cc-tools/_campaign
# unzip lens-strata-bundle.zip into _campaign; then:
cd ~/dev/cc-tools/_campaign && git init -q && git add -A && git commit -qm "campaign docs import"
```

Wherever "_campaign" appears below, read it as this dir.

### 1.2 ccgrep — fresh from the bundle (Dan's decision, July 26)

Dan chose a clean start; do NOT hunt for or reuse the earlier working copy.
**OPERATOR first:** if a previous ccgrep working copy exists on this
machine, Dan moves it aside (e.g. `mv <old> <old>.pre-fresh`) or deletes
it — his call, you don't touch it.

Then:
1. Unzip ccgrep-project.zip to `~/dev/cc-tools/ccgrep`; `git init` +
   commit "import from bundle".
2. Run the suite — expect 14/14 on synthetic fixtures.
3. Re-run Phase 0-1 per ccgrep's own START_HERE.md. Expectations from the
   previous run (treat as reference, verify don't assume): A3/A6/A7/A8
   confirm with zero parser.py changes; the subagent-files finding
   reappears (separate `<parent-sid>/subagents/agent-*.jsonl`, missed by
   the discover glob — re-confirm, still don't fix here); re-create ~3
   sanitized real fixtures (target 17/17); index lands near 187 parent
   sessions / 911 episodes / 782 canonical / 35 repos. Material deviation
   from these numbers = report to Dan, don't rationalize.
4. Record what Phase 0-1 found in ccgrep's ASSUMPTIONS.md as usual — this
   fresh history is now the audit trail.

### 1.3 Verify before proceeding

Tests green in ccgrep (17/17 after fixtures); index built and stats
recorded in ASSUMPTIONS.md; then STOP GATE 1.

### 1.4 File movement plan (when things leave _campaign)

- STRATA.md → copied into the strata repo at its creation (3.1) as the
  founding design doc; the _campaign copy remains the campaign plan.
- FINDINGS.md → born in _campaign (2.4); copied into strata at 4.1 and
  into lens at 4.2 (both consume it as a design input).
- change-lens-mockup.jsx + the SPEC you draft → into the lens repo at 4.2.
- lens_probe.py → stays in _campaign permanently; its watch mode gets
  re-pointed at strata's follow in 3.3.
- Nothing else moves. Repos never import from _campaign at runtime — docs
  travel by copy at repo creation, code lives only in repos.

**STOP GATE 1:** report the fresh Phase 0-1 results vs the reference
numbers. Go/no-go for Stage 2.

---

## STAGE 2 — lens probe (~1 hour, read-only)

Purpose: settle four facts about what session JSONL records around edit
approvals, before the lens SPEC or strata's edits() layer hardens.
Full background: LENS_RUNBOOK.md. You orchestrate; Dan operates Terminal A.

### 2.1 Setup (you do this)

```bash
mkdir -p ~/tmp/lens-fixture && cd ~/tmp/lens-fixture
git init -q
printf 'fixture repo for lens probe\nsecond line\nkeep this line\n' > README.md
printf 'def util_placeholder():\n    return 1\n' > util.py
git add -A && git commit -qm "fixture"
```

Then tell Dan the terminal layout:
- **Terminal A (OPERATOR):** `cd ~/tmp/lens-fixture && claude` — default
  permission mode; being asked for approval is the point.
- **Terminal B (you or Dan):** `python3 lens_probe.py watch ~/.claude/projects/-<dash-encoded-fixture-path>`
  (cwd dash-encoding confirmed in Phase 0/A3; verify the dir appears once
  the session starts). Note the `# watching <path>` line — that path is
  Stage 2.4's input.

### 2.2 The four acts (OPERATOR, exact prompts)

Walk Dan through one act at a time; confirm each completed before the next:

- **Act A (approve + THE Q1 OBSERVATION):** prompt: `add a comment line at
  the top of README.md`. When CC asks for approval, Dan stares at Terminal
  B for ~10 seconds BEFORE approving. **Q1 verdict:** did
  `[tool_use Edit ...]` print during the stare (VISIBLE) or only after
  approving (SILENT)? Record it immediately.
- **Act B (deny with reason):** prompt: `delete the last line of README.md`.
  Deny; type as the next message: `no, I want to keep that line`.
- **Act C (deny then revise):** prompt: `add a retry helper function to
  util.py`. Deny the first proposal with: `use a decorator instead`.
  Approve the second proposal.
- **Act D (payload shapes):** prompt: `create a new file notes.md with two
  lines, then change both lines using a single multi-edit`. Approve all.
- **Act E (optional, recommended):** one more trivial edit prompt;
  Esc-interrupt while the approval is pending. Distinguishes
  interrupt-vs-deny on disk.

Exit the CC session.

### 2.3 Inspect (you do this)

```bash
python3 lens_probe.py inspect <session.jsonl from the watch line>
```

If the path is lost: `ls -t ~/.claude/projects/-<fixture-dir>/*.jsonl | head -1`.
Ignore any `subagents/` subdir — the acts live in the parent file.

### 2.4 Write FINDINGS.md (you draft, Dan confirms Q1)

Create FINDINGS.md next to this runbook:

```
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
```

Fill from the inspect summary (it prints keyed to these IDs). Q1 comes
from Dan's Act-A observation — ask him, don't infer.

### Decision rules (these bind later stages)

- Q1 VISIBLE → lens LIVE face as mocked (amber card, exact hunk pre-approval).
- Q1 SILENT → LIVE degrades to applied-ledger + heuristic "something
  pending" banner; amber hunk card parked behind a hooks/PTY decision v1
  does not take.
- Full-payload gaps → that tool gets file-level rows only.
- Interrupt indistinguishable from deny → single "not applied" fate in v1.
- No revision-linkage field → revised = heuristic (same file + overlapping
  old_string within one episode), labeled heuristic in the SPEC.
- Latency or usage FAIL → drop that feature, no substitutes.

**STOP GATE 2:** present FINDINGS.md to Dan. Go/no-go for Stage 3.

---

## STAGE 3 — strata extraction (the active build)

Read STRATA.md fully first (laws, 5 layers, provenance). Working name
strata — **confirm the name with Dan at repo creation** (his standing
naming pass).

### 3.1 Repo + lift

- Create the strata repo (structure mirroring ccgrep's package discipline;
  stdlib-only, tests alongside modules).
- Move from ccgrep: discovery, parser/records, chunker/episodes + outcome
  stamping, the token-capped JSON serialization util. Tests and the 3
  sanitized real fixtures travel with their modules. ASSUMPTIONS.md format
  entries move too, keeping tags and verification sources.
- ccgrep imports strata; all 17 tests green before anything else.

### 3.2 Subagent fix (first strata-native work item)

- discovery: also emit `<parent-sid>/subagents/agent-*.jsonl` as
  SubagentRef linked to parent (sessionId + agentId from Phase 0 finding).
- episodes: fold subagent entries into parent episodes under the existing
  sidechain-folding rule (errors bubbled, offsets kept). Cross-file
  linkage is the new part — design it in strata, not ccgrep.
- Capture one sanitized subagent fixture; add tests.
- Re-index the corpus. Expect the 86 skipped files to appear and
  episode/error counts to shift — report the before/after numbers to Dan;
  the shift is the fix working.

### 3.3 follow

- Build `follow(ref | dir)` per STRATA.md layer 3 (rotation-aware,
  newest-file tracking, seek-to-end or from-offset).
- Delete the bespoke tails: lens_probe.py watch re-points to follow;
  ccgrep ingest re-points; note Cosmo's probe is out of scope.

### 3.4 Ship

- ccgrep pinned to strata, full suite green, re-index clean.
- Build the wheel for Artifactory. **OPERATOR:** publishing and any git
  push/PR — ask Dan, he runs or approves.

**STOP GATE 3:** summarize what moved, subagent before/after numbers, test
counts. Go/no-go for Stage 4.

---

## STAGE 4 — edits() layer → lens SPEC → lens v1

### 4.1 strata edits() (shape dictated by FINDINGS.md)

Per STRATA.md layer 5: `edits()`, `reconstruct()`, `attribute()`.
- Fate vocabulary from CHECK_denial_shape / CHECK_interrupt_vs_deny /
  CHECK_revision_link per the decision rules above.
- Latency fields iff CHECK_latency_ts passed.
- attribute(): stdlib-ast innermost def/class, at ingest against
  reconstructed post-edit content, never against current files; parse
  failure → file-level + "unparseable" marker. Python-only.

### 4.2 lens SPEC.md (you draft, Dan negotiates)

Must contain: strata dependency declaration (episodes and edits are
consumed, never redefined); the two faces with LIVE set by the Q1 verdict;
three drill levels per change-lens-mockup.jsx; the frozen v1 crop —
copy-as PR description (episodes→markdown via OSC52) + copy-as
patch/resume, rejection reasons verbatim (gated on CHECK_rejection_reason),
command ledger (bash calls + exit codes), per-edit approval latency
(gated), thrash flag (3+ edits same symbol), committed-vs-not footer,
per-episode token/cost rollup (gated on CHECK_usage), compaction/error
markers, symbol attribution; the parking lot — impact graph (v2),
reverse-patch (only with current-content match + `git apply -R --check`
guard), multi-session day view, tree-sitter. Laws: read-only, no AI in the
render loop, degrade-don't-guess.

**STOP GATE 4a:** Dan approves the SPEC before any lens code.

### 4.3 Build lens v1

Second strata consumer — where the API proves it serves someone besides
its donor. Report any strata API friction to Dan as substrate feedback,
don't silently work around it.

**STOP GATE 4:** lens v1 demo on a real session. Go/no-go for Stage 5.

---

## STAGE 5 — reader

Its spec and probe drafts live in the reader chat/bundle — ask Dan to
provide them; do not reinvent. Implement on strata layers 1-4. Naming pass
happens here. Open question owed to STRATA.md §OQ3: does the event
vocabulary need render-oriented events or are writing-indicator chunks
derived from assistant_text deltas — decide and record it.

## Parked (do not raise before Stage 5 completes)

Suite merge ("session instrument"); Cosmo adopting strata.

## If confused

Re-run §State detection, report what you see, ask Dan. Never guess the
stage.
