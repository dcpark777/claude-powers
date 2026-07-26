import json
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "projects"
GOLDEN = json.loads((Path(__file__).parent / "golden.json").read_text())


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    subprocess.run([sys.executable, str(Path(__file__).parent / "make_fixtures.py")],
                   check=True)
    from ccgrep.store import Store
    from ccgrep import search as search_mod
    s = Store(tmp_path_factory.mktemp("db") / "index.db")
    search_mod.index(s, root=FIXTURES)
    return s


def test_recall_at_5(store):
    from ccgrep import search as search_mod
    hits_at_5 = 0
    misses = []
    for case in GOLDEN["cases"]:
        hits = search_mod.search(store, case["query"], limit=5, auto_index=False)
        got = [h.session_id for h in hits]
        if case["expected_session"] in got:
            hits_at_5 += 1
        else:
            misses.append((case["query"], got))
    recall = hits_at_5 / len(GOLDEN["cases"])
    assert recall >= GOLDEN["min_recall_at_5"], f"recall@5={recall:.2f}; misses={misses}"
