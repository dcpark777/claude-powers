import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "projects"


@pytest.fixture(scope="session", autouse=True)
def fixtures():
    subprocess.run([sys.executable, str(Path(__file__).parent / "make_fixtures.py")],
                   check=True)
    return FIXTURES


@pytest.fixture()
def store(tmp_path, fixtures, monkeypatch):
    monkeypatch.setenv("CCGREP_SESSIONS_DIR", str(fixtures))
    monkeypatch.setenv("CCGREP_DB", str(tmp_path / "index.db"))
    from ccgrep.store import Store
    from ccgrep import search as search_mod
    s = Store(tmp_path / "index.db")
    search_mod.index(s, root=fixtures)
    return s


def _parse(name):
    from ccgrep.parser import parse_session
    hits = list(FIXTURES.glob(f"*/{name}.jsonl"))
    assert hits, f"fixture {name} missing"
    return parse_session(hits[0])


def test_parser_tolerates_torn_line(fixtures):
    meta, msgs = _parse("s-torn")
    assert len(msgs) == 2                      # torn third line skipped, no raise
    assert meta.repo == "pipeline"
    assert meta.session_id == "s-torn"


def test_parser_extracts_errors_and_sidechain(fixtures):
    meta, msgs = _parse("s-sidechain")
    side = [m for m in msgs if m.is_sidechain]
    assert side, "sidechain flag not parsed"
    errs = [e for m in msgs for e in m.tool_result_errors]
    assert any("403 Forbidden" in e for e in errs)


def test_chunker_episode_boundaries_and_sidechain_fold(fixtures):
    from ccgrep.chunker import chunk_session
    meta, msgs = _parse("s-sidechain")
    eps = chunk_session(meta, msgs)
    assert len(eps) == 1                       # one prompt → one episode
    ep = eps[0]
    assert ep.had_sidechain
    assert "403 Forbidden" in ep.errors        # sidechain error bubbled up
    assert "artifactory" in ep.identifiers     # identifiers extracted


def test_outcome_green_and_thrash(fixtures):
    from ccgrep.chunker import chunk_session
    from ccgrep.outcome import stamp_outcomes
    meta, msgs = _parse("s-datetime")
    eps = stamp_outcomes(chunk_session(meta, msgs))
    assert eps[0].outcome == "green"
    meta, msgs = _parse("s-thrash")
    eps = stamp_outcomes(chunk_session(meta, msgs))
    assert eps[0].outcome == "thrash"


def test_dedup_clusters_recurring_error(store):
    rows = [r for r in store.all_episodes() if "s-snowflake" in r["id"]]
    exemplars = [r for r in rows if r["canonical_id"] == r["id"]]
    assert len(exemplars) == 1
    assert exemplars[0]["seen_count"] == 3
    # exemplar should be the green (resolved) one
    assert exemplars[0]["outcome"] == "green"
    assert "s-snowflake-3" in exemplars[0]["id"]


def test_search_error_shaped_query(store):
    from ccgrep import search as search_mod
    hits = search_mod.search(store, "CERTIFICATE_VERIFY_FAILED", auto_index=False)
    assert hits and hits[0].session_id == "s-snowflake-3"
    assert hits[0].seen_count == 3


def test_search_intent_query(store):
    from ccgrep import search as search_mod
    hits = search_mod.search(store, "naive datetimes timezone", auto_index=False)
    assert hits and hits[0].session_id == "s-datetime"
    assert hits[0].outcome == "green"


def test_green_filter_and_repo_filter(store):
    from ccgrep import search as search_mod
    hits = search_mod.search(store, "kfp component build", green_only=True,
                             auto_index=False)
    assert all(h.outcome == "green" for h in hits)
    hits = search_mod.search(store, "snowflake", repo="pipeline", auto_index=False)
    assert all(h.repo == "pipeline" for h in hits)


def test_json_door_caps_and_schema(store):
    from ccgrep import search as search_mod
    from ccgrep.render_json import render_search, MAX_HITS_JSON
    hits = search_mod.search(store, "snowflake ssl certificate", auto_index=False)
    out = render_search(hits, "snowflake ssl certificate", token_budget=500)
    payload = json.loads(out)
    assert payload["schema"] == 1
    assert len(payload["hits"]) <= MAX_HITS_JSON
    assert len(out) // 4 + 1 <= 500
    for h in payload["hits"]:
        assert {"id", "ts", "outcome", "seen_count", "snippet"} <= set(h)


def test_json_budget_enforced_under_pressure(store):
    from ccgrep.render_json import render_search
    from ccgrep.search import Hit
    big = [Hit(id=f"x#{i}", session_id="x", repo="r", ts_end="2026-07-01T00:00:00Z",
               outcome="unknown", seen_count=1, score=1.0, prompt="p" * 200,
               snippet="s" * 200, src_path="", start_line=0, end_line=0)
           for i in range(10)]
    out = render_search(big, "q", token_budget=200)
    assert len(out) // 4 + 1 <= 200


def test_show_caps_lines(store):
    from ccgrep import search as search_mod
    rows = [r for r in store.all_episodes() if r["id"].startswith("s-thrash")]
    lines = search_mod.show(store, rows[0]["id"], lines=5)
    assert len(lines) <= 6                     # 5 + cap notice


def test_incremental_index_skips_unchanged(store, fixtures):
    from ccgrep import search as search_mod
    res = search_mod.index(store, root=fixtures)
    assert res["files_indexed"] == 0


def test_cli_json_smoke(store, fixtures, tmp_path, monkeypatch):
    env = dict(os.environ, CCGREP_SESSIONS_DIR=str(fixtures),
               CCGREP_DB=str(store.db_path))
    out = subprocess.run(
        [sys.executable, "-m", "ccgrep.cli", "--json", "search", "artifactory",
         "token"], capture_output=True, text=True, env=env,
        cwd=str(Path(__file__).parent.parent))
    assert out.returncode == 0, out.stderr
    payload = json.loads(out.stdout)
    assert payload["hits"], "expected at least one hit"
    assert payload["hits"][0]["session_id"] == "s-sidechain"
