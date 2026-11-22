import pytest

from jobsearch import adapters, boards, cli
from jobsearch.titles import TitleFilter


def job(title, loc, url, posted="2026-11-20T10:00:00Z"):
    return {"title": title, "location": loc, "primary_location": loc, "url": url, "posted_at": posted}


FEEDS = {
    "acme": [job("Senior Backend Engineer", "Tel Aviv, Israel", "https://x/acme/1"),
             job("Backend Engineer", "New York", "https://x/acme/2"),
             job("Product Manager", "Tel Aviv", "https://x/acme/3")],
    "beta": [job("Backend Engineer Intern", "Haifa", "https://x/beta/1"),
             job("Backend Engineer", "Herzliya", "https://x/beta/2", posted="")],
    "gamma": [],
    "delta": [],
}


def fake_fetch(fail=()):
    def fetch(provider, token, keep=None):
        if token in fail:
            raise OSError("boom")
        return FEEDS[token]
    return fetch


def companies(*names):
    return [{"name": n.title(), "provider": "greenhouse", "token": n} for n in names]


def test_keeps_israeli_accepted_titles(monkeypatch):
    monkeypatch.setattr(adapters, "fetch_jobs", fake_fetch())
    rows, failures = boards.search_boards(companies("acme", "beta", "gamma", "delta"),
                                          TitleFilter(["backend engineer"], ["intern"]).accept)
    assert failures == []
    assert sorted((r["company"], r["title"], r["city"]) for r in rows) == [
        ("Acme", "Senior Backend Engineer", "Tel Aviv, Israel"),
        ("Beta", "Backend Engineer", "Herzliya")]
    assert all(r["source"] == "boards" for r in rows)
    acme = next(r for r in rows if r["company"] == "Acme")
    assert acme["posted"] == "2026-11-20" and acme["url"] == "https://x/acme/1"


def test_one_failing_board_is_tolerated(monkeypatch):
    monkeypatch.setattr(adapters, "fetch_jobs", fake_fetch(fail={"gamma"}))
    rows, failures = boards.search_boards(companies("acme", "beta", "gamma", "delta"),
                                          TitleFilter(["backend engineer"], []).accept)
    assert [f[0] for f in failures] == ["Gamma"] and rows


def test_most_failing_is_broken_run(monkeypatch):
    monkeypatch.setattr(adapters, "fetch_jobs", fake_fetch(fail={"acme", "beta", "gamma"}))
    with pytest.raises(boards.BrokenRun):
        boards.search_boards(companies("acme", "beta", "gamma", "delta"), lambda t: True)


def test_cli_empty_include_exits_2(titles_file, shipped, tmp_path, capsys):
    rc = cli.main(["boards", "--titles", str(titles_file("[include]\n")), "--out", str(tmp_path / "b.csv")])
    assert rc == 2
    assert "no titles in [include]" in capsys.readouterr().err


def test_cli_missing_titles_exits_2(shipped, tmp_path, capsys):
    rc = cli.main(["boards", "--titles", str(tmp_path / "nope.txt"), "--out", str(tmp_path / "b.csv")])
    assert rc == 2 and "nope.txt" in capsys.readouterr().err


def test_cli_bad_company_file_exits_2(titles_file, shipped, tmp_path, capsys):
    (tmp_path / "cfg").mkdir()
    (tmp_path / "cfg" / "companies.json").write_text("[{", encoding="utf-8")
    rc = cli.main(["boards", "--titles", str(titles_file()), "--out", str(tmp_path / "b.csv")])
    assert rc == 2 and "companies.json" in capsys.readouterr().err


def test_cli_broken_run_keeps_old_output(monkeypatch, titles_file, shipped, tmp_path):
    out = tmp_path / "b.csv"
    out.write_text("old", encoding="utf-8")
    monkeypatch.setattr(adapters, "fetch_jobs", fake_fetch(fail={"acme", "beta", "gamma"}))
    assert cli.main(["boards", "--titles", str(titles_file()), "--out", str(out)]) == 1
    assert out.read_text(encoding="utf-8") == "old"


def test_cli_success_writes_and_prints(monkeypatch, titles_file, shipped, tmp_path, capsys):
    out = tmp_path / "sub" / "b.csv"
    monkeypatch.setattr(adapters, "fetch_jobs", fake_fetch(fail={"gamma"}))
    assert cli.main(["boards", "--titles", str(titles_file()), "--out", str(out)]) == 0
    printed = capsys.readouterr()
    assert "Searched 4 company boards (1 failed)" in printed.out
    assert "Found 2 jobs in Israel" in printed.out
    assert "failed: gamma" in printed.err
    assert out.exists()
