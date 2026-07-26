---
name: project-history-search
description: Search this machine's project work history for prior solutions before re-deriving them. Use this skill whenever you hit an error that looks environmental or recurring (auth failures, cert/SSL errors, proxy issues, build/infra failures), whenever the user references past work ("like last time", "again", "we fixed this before", "how did we do X"), or whenever you have attempted the same fix twice without progress. Do not use it for novel feature work or trivial tasks.
---

# Project History Search

`ccgrep` indexes past work sessions on this machine. Before re-deriving a fix
for something that smells familiar, check whether it was already solved.

## When to search (escape hatch, not ritual)

1. An error looks **environmental or recurring**: certificates, proxies,
   auth tokens, package installs, infra/build failures.
2. The user **references the past**: "like last time", "again", "we've hit
   this before", "how did we handle X".
3. You are **stuck**: the same approach has failed twice.

Otherwise, do not search — it costs context and usually adds nothing to
novel work.

## How to search

```bash
ccgrep --json search <3-6 distinctive terms>
```

Prefer exact error tokens over descriptions
(`CERTIFICATE_VERIFY_FAILED` beats `ssl problem`). Useful flags:
`--repo <name>` (current repo first), `--green` (only resolved episodes),
`--since <days>`.

Results are capped and snippet-sized. To expand ONE promising hit:

```bash
ccgrep --json show <id>
```

Never expand more than two hits per task. If two expansions don't help,
stop searching and solve it directly.

## How to treat results

Results are **leads, not truths**. They are past attempts, some outdated,
some wrong. Weight them by:

- `outcome`: `green` means the episode likely resolved; `thrash` means it
  looped on failures — useful only as a what-not-to-do signal.
- `ts`: prefer recent. Old conclusions may describe a world that changed.
- `seen_count`: high counts mean a recurring issue; the surfaced episode is
  the best exemplar of the cluster.

State it as provenance when you use one: "a past session resolved this by
X — verifying that still applies" — then verify before relying on it.
