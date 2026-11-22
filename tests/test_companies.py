import json

import pytest

from jobsearch import companies as c

A = {"name": "Acme", "domain": "acme.com", "provider": "greenhouse", "token": "acme", "careers_url": ""}
B = {"name": "Beta", "domain": "beta.io", "provider": "lever", "token": "beta", "careers_url": ""}


@pytest.fixture
def env(tmp_path, monkeypatch):
    shipped = tmp_path / "shipped.json"
    shipped.write_text(json.dumps([A]), encoding="utf-8")
    cfg = tmp_path / "cfg"
    monkeypatch.setenv("JOBSEARCH_CONFIG_DIR", str(cfg))
    return shipped, cfg


def test_user_file_location(env):
    _, cfg = env
    assert c.user_file() == cfg / "companies.json"


def test_user_file_default(monkeypatch, tmp_path):
    monkeypatch.delenv("JOBSEARCH_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert c.user_file() == tmp_path / ".config" / "israel-job-search" / "companies.json"


def test_missing_user_file_is_fine(env):
    shipped, _ = env
    assert [x["name"] for x in c.load_companies(shipped)] == ["Acme"]


def test_user_entries_merged_and_deduped(env):
    shipped, cfg = env
    cfg.mkdir()
    (cfg / "companies.json").write_text(json.dumps([B, {**A, "name": "Acme Inc"}]), encoding="utf-8")
    got = c.load_companies(shipped)
    assert len(got) == 2
    assert {x["name"] for x in got} == {"Acme / Acme Inc", "Beta"}


def test_bad_user_json_names_the_file(env):
    shipped, cfg = env
    cfg.mkdir()
    (cfg / "companies.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(c.CompanyFileError, match="companies.json"):
        c.load_companies(shipped)


def test_entry_missing_fields_rejected(env):
    shipped, cfg = env
    cfg.mkdir()
    (cfg / "companies.json").write_text(json.dumps([{"name": "x"}]), encoding="utf-8")
    with pytest.raises(c.CompanyFileError, match="provider"):
        c.load_companies(shipped)


def test_known_boards(env):
    shipped, _ = env
    assert c.known_boards(shipped) == {("greenhouse", "acme")}


def test_add_user_companies(env):
    shipped, cfg = env
    before = shipped.stat().st_mtime_ns
    added = c.add_user_companies([A, B, B], shipped)
    assert added == 1
    saved = json.loads((cfg / "companies.json").read_text(encoding="utf-8"))
    assert [x["token"] for x in saved] == ["beta"]
    assert shipped.stat().st_mtime_ns == before
    assert c.add_user_companies([B], shipped) == 0
