from jobsearch import adapters, cli, techmap
from jobsearch.titles import TitleFilter

HEADER = '﻿"company","category","size","title","level","city","url","updated"\n'
SAMPLE = HEADER + (
    '"Acme","Cyber","l","Senior Backend Engineer","Senior","תל אביב-יפו","https://www.comeet.com/jobs/acme/1?utm_source=techmap","2026-11-20"\n'
    '"Beta","Fintech","m","Backend Engineer Intern","Junior","Haifa","https://b/2","2026-11-21"\n'
    '"Gamma","Data","s","Data Analyst","Mid","Herzliya","https://g/3","2026-11-19"\n'
)


def test_categories_are_the_19_files():
    assert len(techmap.CATEGORIES) == 19 and "software" in techmap.CATEGORIES and "hr" in techmap.CATEGORIES


def test_parse_csv_bom_hebrew_and_filter():
    rows = techmap.parse_csv(SAMPLE.lstrip("﻿"), TitleFilter(["backend engineer"], ["intern"]).accept)
    assert rows == [{"company": "Acme", "title": "Senior Backend Engineer", "city": "תל אביב-יפו",
                     "posted": "2026-11-20", "url": "https://www.comeet.com/jobs/acme/1?utm_source=techmap",
                     "source": "techmap"}]


def test_parse_csv_with_bom_header():
    rows = techmap.parse_csv(SAMPLE, lambda t: True)
    assert len(rows) == 3 and rows[0]["company"] == "Acme"


def test_same_url_in_two_categories_once(monkeypatch):
    monkeypatch.setattr(adapters, "http_get_text", lambda url, retries=2: SAMPLE)
    rows, failed = techmap.search_techmap(lambda t: True)
    assert failed == [] and len(rows) == 3


def test_failed_categories_reported(monkeypatch):
    def get(url, retries=2):
        if "software" in url:
            raise OSError("down")
        return SAMPLE
    monkeypatch.setattr(adapters, "http_get_text", get)
    rows, failed = techmap.search_techmap(lambda t: True)
    assert failed == ["software"] and len(rows) == 3


def test_cli_all_fail_exits_1(monkeypatch, titles_file, tmp_path):
    def get(url, retries=2):
        raise OSError("down")
    monkeypatch.setattr(adapters, "http_get_text", get)
    out = tmp_path / "t.csv"
    assert cli.main(["techmap", "--titles", str(titles_file()), "--out", str(out)]) == 1
    assert not out.exists()


def test_cli_ok(monkeypatch, titles_file, tmp_path, capsys):
    monkeypatch.setattr(adapters, "http_get_text", lambda url, retries=2: SAMPLE)
    out = tmp_path / "t.csv"
    assert cli.main(["techmap", "--titles", str(titles_file()), "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "Found 1 jobs in techmap (LinkedIn via techmap)" in text and out.exists()
