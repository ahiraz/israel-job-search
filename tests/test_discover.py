import json

from jobsearch import adapters, cli, discover


def test_extract_boards_shapes():
    urls = [
        "https://job-boards.greenhouse.io/daylightsecurity",
        "https://job-boards.greenhouse.io/daylightsecurity/jobs/123?gh_src=x",
        "https://boards.eu.greenhouse.io/Euro",
        "https://jobs.ashbyhq.com/acme-ai/abc-uuid",
        "https://jobs.lever.co/levco/1f2e-uuid",
        "https://jobs.smartrecruiters.com/SmartCo/7438",
        "https://foo.recruitee.com/o/backend",
        "https://www.comeet.com/jobs/cycode/A8.00D/backend-engineer/FF.049",
        "https://boards.greenhouse.io/embed/job_board?for=embedded",
        "https://job-boards.greenhouse.io/jobs",
        "https://example.com/careers",
    ]
    assert discover.extract_boards(urls) == [
        ("greenhouse", "daylightsecurity"),
        ("greenhouse", "euro"),
        ("ashby", "acme-ai"),
        ("lever", "levco"),
        ("smartrecruiters", "smartco"),
        ("recruitee", "foo"),
        ("comeet", "cycode/A8.00D"),
        ("greenhouse", "embedded"),
    ]


def test_resolve_comeet(monkeypatch):
    page = 'var x = {company_uid: "A8.00D", token: "AB12CD34EF56AB12CD34EF56AB12"};'
    monkeypatch.setattr(adapters, "http_get_text", lambda url, retries=2: page)
    assert discover.resolve_comeet("cycode", "A8.00D") == "A8.00D::AB12CD34EF56AB12CD34EF56AB12"


def test_resolve_comeet_api_url_form(monkeypatch):
    page = '<a href="https://www.comeet.co/careers-api/2.0/company/A8.00D/positions?token=FFEE11223344556677889900AA">'
    monkeypatch.setattr(adapters, "http_get_text", lambda url, retries=2: page)
    assert discover.resolve_comeet("cycode", "A8.00D") == "A8.00D::FFEE11223344556677889900AA"


def test_resolve_comeet_no_token(monkeypatch):
    monkeypatch.setattr(adapters, "http_get_text", lambda url, retries=2: "<html></html>")
    assert discover.resolve_comeet("cycode", "A8.00D") is None


def il(title):
    return {"title": title, "location": "Tel Aviv", "primary_location": "Tel Aviv", "url": "u"}


def us(title):
    return {"title": title, "location": "New York", "primary_location": "New York", "url": "u"}


def test_verify(monkeypatch):
    feeds = {"good": [il("a"), il("b"), us("c")], "usonly": [us("a")]}

    def fetch(provider, token, keep=None):
        if token not in feeds:
            raise OSError("404")
        return feeds[token]
    monkeypatch.setattr(adapters, "fetch_jobs", fetch)
    monkeypatch.setattr(discover, "board_name", lambda p, t: t.title())
    assert discover.verify("greenhouse", "good") == {
        "name": "Good", "domain": "", "provider": "greenhouse", "token": "good",
        "careers_url": "https://job-boards.greenhouse.io/good", "jobs_israel": 2}
    assert discover.verify("greenhouse", "usonly") is None


def test_cli_discover_reports_and_saves(monkeypatch, tmp_path, shipped, capsys):
    urls = tmp_path / "urls.txt"
    urls.write_text("\n".join([
        "https://job-boards.greenhouse.io/acme",          # in shipped list -> known
        "https://job-boards.greenhouse.io/newco/jobs/1",  # new, Israeli jobs
        "https://jobs.lever.co/usco",                     # US only
        "https://jobs.ashbyhq.com/gone",                  # fetch fails
    ]), encoding="utf-8")
    feeds = {"newco": [il("Backend")], "usco": [us("x")]}

    def fetch(provider, token, keep=None):
        if token not in feeds:
            raise OSError("404")
        return feeds[token]
    monkeypatch.setattr(adapters, "fetch_jobs", fetch)
    monkeypatch.setattr(discover, "board_name", lambda p, t: t.title())

    report_file = tmp_path / "report.json"
    assert cli.main(["discover", "--urls", str(urls), "--report", str(report_file)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert [n["token"] for n in report["new"]] == ["newco"]
    reasons = {s["board"]: s["reason"] for s in report["skipped"]}
    assert reasons == {"greenhouse/acme": "known", "lever/usco": "no israeli jobs",
                       "ashby/gone": "fetch failed"}
    assert not (tmp_path / "cfg" / "companies.json").exists()

    assert cli.main(["discover", "--save", str(report_file)]) == 0
    out = capsys.readouterr().out
    assert "Added 1 companies to" in out
    saved = json.loads((tmp_path / "cfg" / "companies.json").read_text(encoding="utf-8"))
    assert [s["token"] for s in saved] == ["newco"]


def test_known_comeet_matched_by_uid(monkeypatch, tmp_path, shipped, capsys):
    data = json.loads(shipped.read_text())
    data.append({"name": "Cycode", "provider": "comeet", "token": "A8.00D::SOMETOKEN"})
    shipped.write_text(json.dumps(data))
    urls = tmp_path / "u.txt"
    urls.write_text("https://www.comeet.com/jobs/cycode/A8.00D/x/1")
    assert cli.main(["discover", "--urls", str(urls)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["new"] == [] and report["skipped"][0]["reason"] == "known"


def test_save_uses_the_approved_report_without_refetching(monkeypatch, tmp_path, shipped, capsys):
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"new": [{"name": "NewCo", "domain": "", "provider": "greenhouse",
                                           "token": "newco", "careers_url": "", "jobs_israel": 2}],
                                  "skipped": []}), encoding="utf-8")

    def boom(*a, **k):
        raise AssertionError("--save must not fetch")
    monkeypatch.setattr(adapters, "fetch_jobs", boom)
    assert cli.main(["discover", "--save", str(report)]) == 0
    assert "Added 1 companies to" in capsys.readouterr().out
    saved = json.loads((tmp_path / "cfg" / "companies.json").read_text(encoding="utf-8"))
    assert [s["token"] for s in saved] == ["newco"]


def test_discover_writes_report_file(monkeypatch, tmp_path, shipped, capsys):
    urls = tmp_path / "u.txt"
    urls.write_text("https://job-boards.greenhouse.io/newco")
    monkeypatch.setattr(adapters, "fetch_jobs", lambda p, t, keep=None: [il("x")])
    monkeypatch.setattr(discover, "board_name", lambda p, t: "NewCo")
    report = tmp_path / "r.json"
    assert cli.main(["discover", "--urls", str(urls), "--report", str(report)]) == 0
    assert json.loads(report.read_text())["new"][0]["token"] == "newco"
