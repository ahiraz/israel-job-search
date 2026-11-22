import json

import pytest


@pytest.fixture
def titles_file(tmp_path):
    def make(text="[include]\nbackend engineer\n[exclude]\nintern\n"):
        p = tmp_path / "titles.txt"
        p.write_text(text, encoding="utf-8")
        return p
    return make


@pytest.fixture
def shipped(tmp_path, monkeypatch):
    """A 4-board shipped list and an empty personal config dir."""
    boards = [{"name": n, "domain": f"{n}.com", "provider": "greenhouse", "token": n, "careers_url": ""}
              for n in ("acme", "beta", "gamma", "delta")]
    p = tmp_path / "companies.json"
    p.write_text(json.dumps(boards), encoding="utf-8")
    monkeypatch.setenv("JOBSEARCH_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr("jobsearch.companies.SHIPPED", p)
    return p
