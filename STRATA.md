# STRATA.md — strata, the shared session layer

One library that reads Claude Code session JSONL so no tool ever parses it
again. Extracted from ccgrep (the third time this code was written was the
last). Products stay separate binaries; merging them into one "session
instrument" is a v2 decision made only after two consumers ship and the
overlap is felt, not theorized.

Name: **strata** (working name, chosen July 2026 — sessions settle
passively into layers; the lib reads the record). Confirm or revisit at
repo creation in step 3 of the sequence. ccgrep keeps its name.
"substrate" below refers to the role, i.e. this library.

## Consumers

| Tool | Uses | Status |
|------|------|--------|
| ccgrep | layers 1-4 (donor: these move out of it) | core built, pre-Phase-1 |
| lens | layers 1-5 + git correlation (lens-side) | probe stage |
| reader | layers 1-4 live (`follow`) + jump-to-moment via episodes | spec stage |
| Cosmo | possible future consumer | explicitly OUT of scope for now |
| mission (Historian) | possible future consumer via JSON doors | not planned |

## Laws

1. **Read-only.** The substrate never writes outside its own cache/index dirs.
2. **JSONL only.** No git, no process tables, no network. Git correlation is
   consumer policy (lens), process mapping is consumer policy (Cosmo, later).
3. **Quirk quarantine.** Every CC format oddity lives in the records layer and
   nowhere else. Consumers never see raw JSONL shapes.
4. **Degrade, don't guess.** Parse failures and ambiguity produce coarser
   truth (file-level rows, "unparseable" markers), never fabricated detail.
   This law lives in the substrate so every consumer inherits it.
5. **No AI anywhere.** Deterministic core; AI stays at the consumers' edges
   if it appears at all.
6. **Stdlib-only.** TUI/render deps belong to products, not the lib.
7. **Capped doors.** The token-capped JSON serialization util ships here, so
   every agent-facing door (ccgrep --json, lens JSON door, future Historian
   feeds) inherits the same cap discipline for free.

## Layers

### 1. Discovery  — exists in ccgrep, moves
    sessions(root) -> [SessionRef]        # path, repo/project, mtime, session_id
    resolve(spec) -> SessionRef           # id | "latest" | repo path

### 2. Records  — exists in ccgrep (parser), moves
    records(ref) -> Iterator[Record]      # normalized, schema-tolerant
Format knowledge is versioned: ADAPTER_FACTS notes per CC release; ccgrep's
ASSUMPTIONS.md entries that concern format move here with their tags
(several pre-confirmed by Cosmo Phase 0: encoding scheme, isSidechain,
tool_use:AskUserQuestion, --resume same-session-id).

### 3. Events + Follow  — new (unifies three existing tails)
    events(ref) -> Iterator[Event]        # prompt | assistant_text | tool_use
                                          # | tool_result | error | compaction | usage
    follow(ref | dir) -> Iterator[Event]  # live tail: rotation-aware, newest-file
                                          # tracking, seek-to-end or from-offset
Replaces the tails written separately for the Cosmo probe, the lens probe,
and ccgrep ingest. Blocking iterator is the primitive; callback/async
wrappers are consumer sugar.

### 4. Episodes  — exists in ccgrep (chunker + outcome), moves
    episodes(ref) -> [Episode]            # one user prompt → next prompt
Boundaries, retry splits, sidechain folding (errors bubbled, offsets kept),
outcome stamping including clean_finish (errors-then-resolved stamps green),
error-string extraction, drill offsets back into records. lens and reader
consume this definition; neither redefines an episode.

### 5. Edit fates  — new, GATED on lens probe findings
    edits(ref) -> [EditFate]              # paired tool_use/tool_result for
                                          # Edit/Write/MultiEdit/NotebookEdit
    reconstruct(ref, edit) -> str         # post-edit file content from payloads
    attribute(ref, edit) -> Symbol|File   # stdlib-ast innermost def/class;
                                          # ingest-time only; degrades to file
Fate vocabulary (applied / revised / not-applied vs a distinct rejected
state) is set by LENS_RUNBOOK findings: CHECK_denial_shape,
CHECK_interrupt_vs_deny, CHECK_revision_link, CHECK_full_strings. Latency
fields included iff CHECK_latency_ts passes. Attribution obeys Law 4:
attribute at ingest against reconstructed post-edit content, never against
drifted current files; Python-only in v1 (tree-sitter is a v2 question).

## Out of scope (v1)

- Session state machine + Detail struct (deferred with Cosmo, which owns
  that vocabulary today)
- Search, ranking, indexing, TUI (ccgrep the product keeps these)
- Rendering of any kind
- Git, processes, network

## Extraction gate and order

**Gate: after ccgrep Phase 1.** ccgrep's parser and chunker must first
survive real session files (START_HERE Phase 0-1: format verification +
corpus indexing). Extracting before that just relocates unproven code.

Order once gated:
1. Lift layers 1, 2, 4 out of ccgrep into the lib; ccgrep becomes the first
   consumer. Mostly a move — tests travel with their modules.
2. Build layer 3; delete the three bespoke tails; re-point ccgrep ingest
   and the lens/Cosmo probes' watch modes at `follow`.
3. Build layer 5 once lens FINDINGS.md exists; its shape is dictated there.
4. reader consumes at spec-implementation time; Cosmo adoption is a later,
   independent decision.

## Sequence across projects

Ordered by what each stage proves for the next. Discipline: probes can
share an evening; builds cannot share a month — one active build at a time.

1. **ccgrep Phase 0-1** (work-machine evening #1). Real-file format
   verification + corpus indexing. Gates everything; search starts paying
   rent immediately.
2. **lens probe** (same or next sitting — independent of ccgrep's outcome).
   Produce FINDINGS.md; Q1 pending-visibility decides lens's LIVE face
   before any spec hardens.
3. **Extract the substrate** (gate passed). Lift 1/2/4, build `follow`,
   delete the bespoke tails; ccgrep becomes consumer #1 and continues its
   remaining phases (real golden set ≥0.8, skill-in-anger, TUI week) on top
   of the lib. Naming pass happens here — this is when a repo exists.
4. **lens: edit-fates → SPEC → build.** FINDINGS dictates the fate
   vocabulary; the spec declares the substrate dependency; lens is
   consumer #2 — first proof the API serves someone besides its donor.
5. **reader implementation last, deliberately.** The headline bet inherits
   layers 1-4 proven by two shipping consumers plus its own drafted
   terminal probes; the October reader is far cheaper than the July one.

Parked until step 5 completes (cheap to decide later, expensive now):
the suite-merge question ("session instrument") and Cosmo's substrate
adoption.

## Conformance

- ccgrep's 14 tests (incl. the golden recall@5 harness) move with their
  modules; recall tests stay product-side, parser/chunker tests come along.
- Synthetic fixture corpus lives in the substrate repo and grows a real-file
  scrubbed corpus after Phase 1.
- ASSUMPTIONS.md discipline continues: every format assumption tagged, with
  its verification status and source (Cosmo Phase 0 / ccgrep Phase 1 / lens
  probe).

## Distribution

Internal Artifactory wheel; each product pins a version. Public later if the
products go public — the lib's independence is part of the "missing
observability layer" story but is not itself the headline.

## Open questions

1. ~~Name~~ — strata (working); final confirm at repo creation.
2. Does `attribute()` belong in the lib or in lens? (Here for now per Law 4
   inheritance; revisit if lens stays its only caller through v1.)
3. Event vocabulary completeness — does reader need render-oriented events
   (writing-indicator chunks) or does it derive them from assistant_text
   deltas? Decide at reader implementation.
4. Scrubbed real-file fixture policy (what sanitization makes a captured
   session shareable inside the repo).
