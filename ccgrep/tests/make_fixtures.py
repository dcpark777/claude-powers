"""Generate synthetic session JSONL files matching the ASSUMED CC format.

These encode the same assumptions as parser.py. On the work machine, replace
these with sanitized real snippets and re-run the suite (START_HERE Phase 0).

Sessions generated:
  s-snowflake-1/2/3  — the same Snowflake SSL error hit 3x in repo 'pipeline'
                       (dedup + top-errors material); #3 resolves green
  s-datetime        — a datetime tz bug fixed cleanly in repo 'dataio' (green)
  s-thrash          — a KFP episode that loops the same error 4x (thrash)
  s-sidechain       — a session using a subagent whose errors must bubble up
  s-torn            — live session with a torn final line (parser tolerance)
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent / "fixtures" / "projects"


def entry(etype, content, *, sid, cwd, ts, line_extras=None, sidechain=False):
    e = {
        "type": etype,
        "message": {"role": etype, "content": content},
        "sessionId": sid,
        "cwd": cwd,
        "gitBranch": "main",
        "timestamp": ts,
        "uuid": f"u-{ts}",
        "isSidechain": sidechain,
    }
    if line_extras:
        e.update(line_extras)
    return e


def text(t):
    return [{"type": "text", "text": t}]


def tool_use(name, **inp):
    return {"type": "tool_use", "name": name, "input": inp}


def tool_result(t, is_error=False):
    return {"type": "tool_result", "is_error": is_error,
            "content": [{"type": "text", "text": t}]}


SSL_ERR = ("snowflake.connector.errors.OperationalError: 250003: "
           "SSL: CERTIFICATE_VERIFY_FAILED certificate verify failed: "
           "unable to get local issuer certificate")


def snowflake_session(n, resolves):
    sid = f"s-snowflake-{n}"
    cwd = "/repos/pipeline"
    ts = lambda i: f"2026-07-{10+n:02d}T10:{i:02d}:00Z"
    lines = [
        entry("user", text("run the snowflake backfill for july"), sid=sid, cwd=cwd, ts=ts(0)),
        entry("assistant", [
            *text("Running the backfill script."),
            tool_use("Bash", command="python backfill.py --month 2026-07"),
        ], sid=sid, cwd=cwd, ts=ts(1)),
        entry("user", [tool_result(SSL_ERR, is_error=True)], sid=sid, cwd=cwd, ts=ts(2)),
    ]
    if resolves:
        lines += [
            entry("assistant", [
                *text("This is the corporate proxy MITM cert issue. Fix: point "
                      "REQUESTS_CA_BUNDLE and SNOWFLAKE_CA at the internal CA bundle."),
                tool_use("Bash", command="export REQUESTS_CA_BUNDLE=/etc/ssl/corp-ca.pem && python backfill.py --month 2026-07"),
            ], sid=sid, cwd=cwd, ts=ts(3)),
            entry("user", [tool_result("Backfill complete: 31 partitions written")],
                  sid=sid, cwd=cwd, ts=ts(4)),
            entry("assistant", text("Done — backfill completed after setting the internal CA bundle."),
                  sid=sid, cwd=cwd, ts=ts(5)),
        ]
    else:
        lines += [
            entry("assistant", text("Hit an SSL verification failure; giving up for now."),
                  sid=sid, cwd=cwd, ts=ts(3)),
        ]
    return sid, lines


def datetime_session():
    sid, cwd = "s-datetime", "/repos/dataio"
    ts = lambda i: f"2026-07-20T14:{i:02d}:00Z"
    return sid, [
        entry("user", text("why does load_partition return naive datetimes? tests are failing on tz compare"), sid=sid, cwd=cwd, ts=ts(0)),
        entry("assistant", [
            *text("The parquet reader drops tzinfo. Fix is to localize to UTC in load_partition."),
            tool_use("Edit", file_path="dataio/loaders.py", old_str="x", new_str="y"),
            tool_use("Bash", command="pytest tests/test_loaders.py -q"),
        ], sid=sid, cwd=cwd, ts=ts(1)),
        entry("user", [tool_result("14 passed in 2.1s")], sid=sid, cwd=cwd, ts=ts(2)),
        entry("assistant", text("All green — localized timestamps to UTC at the read boundary in load_partition."), sid=sid, cwd=cwd, ts=ts(3)),
    ]


def thrash_session():
    sid, cwd = "s-thrash", "/repos/pipeline"
    ts = lambda i: f"2026-07-21T09:{i:02d}:00Z"
    lines = [entry("user", text("fix the kfp component build"), sid=sid, cwd=cwd, ts=ts(0))]
    for i in range(4):
        lines += [
            entry("assistant", [tool_use("Bash", command="kfp component build .")],
                  sid=sid, cwd=cwd, ts=ts(1 + i * 2)),
            entry("user", [tool_result(
                "kfp.exceptions.ComponentBuildError: base image pull failed",
                is_error=True)], sid=sid, cwd=cwd, ts=ts(2 + i * 2)),
        ]
    lines.append(entry("assistant", text("Still failing on the base image pull."),
                       sid=sid, cwd=cwd, ts=ts(9)))
    return sid, lines


def sidechain_session():
    sid, cwd = "s-sidechain", "/repos/dataio"
    ts = lambda i: f"2026-07-22T16:{i:02d}:00Z"
    return sid, [
        entry("user", text("audit the artifactory publish workflow"), sid=sid, cwd=cwd, ts=ts(0)),
        entry("assistant", [
            *text("Delegating the scan to a subagent."),
            tool_use("Task", description="scan publish workflow", prompt="scan it"),
        ], sid=sid, cwd=cwd, ts=ts(1)),
        entry("assistant", [tool_use("Bash", command="twine upload --repository artifactory dist/*")],
              sid=sid, cwd=cwd, ts=ts(2), sidechain=True),
        entry("user", [tool_result(
            "HTTPError: 403 Forbidden: artifactory token expired", is_error=True)],
            sid=sid, cwd=cwd, ts=ts(3), sidechain=True),
        entry("assistant", text("Subagent found the publish failing on an expired Artifactory token; rotate via the vault job."), sid=sid, cwd=cwd, ts=ts(4)),
        entry("user", [tool_result("token rotated; upload succeeded")], sid=sid, cwd=cwd, ts=ts(5)),
    ]


def torn_session():
    sid, cwd = "s-torn", "/repos/pipeline"
    return sid, [
        entry("user", text("check the spark job memory settings"), sid=sid, cwd=cwd,
              ts="2026-07-23T11:00:00Z"),
        entry("assistant", [
            *text("Looking at spark.executor.memory now."),
            tool_use("Read", file_path="conf/spark.yaml"),
        ], sid=sid, cwd=cwd, ts="2026-07-23T11:01:00Z"),
    ]


def main():
    sessions = [
        snowflake_session(1, resolves=False),
        snowflake_session(2, resolves=False),
        snowflake_session(3, resolves=True),
        datetime_session(),
        thrash_session(),
        sidechain_session(),
        torn_session(),
    ]
    for sid, lines in sessions:
        d = ROOT / "-repos-pipeline" if "/pipeline" in lines[0]["cwd"] else ROOT / "-repos-dataio"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{sid}.jsonl"
        with open(p, "w") as fh:
            for ln in lines:
                fh.write(json.dumps(ln) + "\n")
            if sid == "s-torn":
                fh.write('{"type":"assistant","message":{"role":"assistant","con')
    print(f"fixtures written under {ROOT}")


if __name__ == "__main__":
    main()
