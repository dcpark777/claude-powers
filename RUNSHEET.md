# RUNSHEET — what to do, in order, with which bundle

Two bundles total:
- **A: ccgrep-project.zip** (from the ccgrep chat) — built package + tests +
  SPEC / ASSUMPTIONS / START_HERE
- **B: lens-strata-bundle.zip** (this chat) — STRATA.md, LENS_RUNBOOK.md,
  lens_probe.py, change-lens-mockup.jsx

Discipline: probes can share an evening; one active build at a time.

## Evening 1 — bundle A (ccgrep)

1. Transfer bundle A to the work machine, unpack into your projects dir.
2. Run the test suite first — 14/14 on synthetic fixtures confirms the
   environment before real files enter the picture.
3. **Phase 0** (per START_HERE): verify format assumptions against real
   `~/.claude/projects` JSONL; update ASSUMPTIONS.md tags with what real
   files confirm or contradict.
4. **Phase 1**: index your real corpus; run a handful of genuine searches;
   note recall impressions (the real golden set is Phase 2, later).

**Gate check:** parser + chunker survived real files → the strata
extraction is unlocked. If Phase 0 surprises are big, fix in ccgrep first —
nothing gets extracted until this passes.

## Evening 2 (or same sitting) — bundle B (lens probe)

5. Unpack bundle B. Put STRATA.md somewhere visible outside both projects —
   it's the umbrella plan, not a project file.
6. Run the scripted session per LENS_RUNBOOK.md: Terminal A = claude in a
   throwaway repo, Terminal B = `python3 lens_probe.py watch <project-dir>`.
   Four acts: approve / deny-with-reason / deny-then-revise / Write+MultiEdit.
   The Q1 moment is Act A's 10-second stare.
7. Run `lens_probe.py inspect <session.jsonl>`; fill the FINDINGS.md
   template from the runbook. Optional Act E: interrupt-vs-deny.

Independent of Evening 1's outcome — these two evenings can swap order if
convenient, but both must finish before steps below.

## Step 3 — strata extraction (gated on Phase 1)

8. Create the repo; confirm the name (strata is the working pick).
9. Lift discovery / records / episodes out of ccgrep — a move, tests travel
   with modules. Build `follow` (one tail); delete the bespoke tails in the
   probes' watch modes and ccgrep ingest; re-point everything at it.
10. ccgrep becomes consumer #1: pin strata, then continue its own Phases
    2-4 (real golden set ≥0.8 → skill-in-anger → TUI week) on top of it.
11. Publish the wheel to Artifactory.

## Step 4 — lens (needs FINDINGS.md)

12. Build strata's edit-fates layer; FINDINGS dictates the fate vocabulary
    (applied / revised / not-applied vs distinct rejected) and whether
    latency ships.
13. Write the lens SPEC: declares the strata dependency, sets the LIVE face
    per the Q1 verdict (visible → amber hunk card as mocked; silent →
    applied-ledger + heuristic banner), freezes the adopted crop
    (copy-as-PR, rejection reasons, command ledger, latency, thrash flag,
    committed-vs-not, cost rollup, markers, symbol attribution).
    change-lens-mockup.jsx is the design reference.
14. Build lens v1 — the second strata consumer, first proof the API serves
    someone besides its donor.

## Step 5 — reader (last, deliberately)

15. Run reader's own terminal probes (from its spec chat), then implement
    on strata layers 1-4. Naming pass happens here.

## Parked until step 5 completes

- Suite merge ("session instrument")
- Cosmo adopting strata

## If lost mid-evening

STRATA.md → "Sequence across projects" is the answer key.
