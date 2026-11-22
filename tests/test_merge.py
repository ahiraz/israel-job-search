import datetime

from jobsearch import cli, merge, output


def row(company, title, url, source, posted=""):
    return {"company": company, "title": title, "city": "Tel Aviv", "posted": posted, "url": url, "source": source}


def test_normalize_url():
    assert merge.normalize_url("HTTPS://WWW.Comeet.com/jobs/x/1/?utm_source=techmap#a") == "https://www.comeet.com/jobs/x/1"


def test_same_url_with_utm_merges():
    a = row("Acme", "Backend Engineer", "https://www.comeet.com/jobs/acme/1", "boards", "2026-11-20")
    b = row("Acme", "Backend Engineer", "https://www.comeet.com/jobs/acme/1?utm_source=techmap", "techmap", "2026-11-22")
    got = merge.merge([a], [b])
    assert len(got) == 1
    assert got[0]["source"] == "boards + techmap"
    assert got[0]["posted"] == "2026-11-20"
    assert got[0]["url"] == "https://www.comeet.com/jobs/acme/1"


def test_same_company_and_title_different_urls_merge():
    a = row("Acme Ltd.", "Sr. Backend Engineer", "https://boards/1", "boards")
    b = row("acme ltd", "Sr Backend Engineer", "https://linkedin/9", "techmap")
    got = merge.merge([a], [b])
    assert len(got) == 1 and got[0]["source"] == "boards + techmap"


def test_different_titles_kept_apart():
    got = merge.merge([row("Acme", "Backend Engineer", "u1", "boards")],
                      [row("Acme", "Frontend Engineer", "u2", "techmap")])
    assert len(got) == 2


def test_source_order_is_boards_first_even_if_techmap_seen_first():
    got = merge.merge([row("A", "T", "u", "techmap")], [row("A", "T", "u", "boards")])
    assert got[0]["source"] == "boards + techmap"


def test_order_newest_first_undated_last():
    got = merge.merge([row("A", "x", "1", "boards", "2026-01-01"), row("B", "y", "2", "boards")],
                      [row("C", "z", "3", "techmap", "2026-11-01")])
    assert [r["company"] for r in got] == ["C", "A", "B"]


def test_cli_merge(tmp_path, capsys):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    output.write_csv([row("Acme", "Backend Engineer", "https://x/1", "boards", "2026-11-20")], a)
    output.write_csv([row("Acme", "Backend Engineer", "https://x/1?utm=1", "techmap"),
                      row("Beta", "QA", "https://y/2", "techmap")], b)
    out = tmp_path / "jobs"
    rc = cli.main(["merge", "--inputs", str(a), str(b), str(tmp_path / "missing.csv"),
                   "--out-dir", str(out), "--heading", "Backend Engineer"])
    assert rc == 0
    cap = capsys.readouterr()
    assert "2 jobs · 2 companies · 1 duplicates merged" in cap.out
    assert "missing.csv" in cap.err
    today = datetime.date.today().isoformat()
    assert (out / f"{today}.md").exists()
    assert len(output.read_csv(out / f"{today}.csv")) == 2


def test_cli_merge_no_inputs_exits_1(tmp_path):
    assert cli.main(["merge", "--inputs", str(tmp_path / "x.csv"), "--out-dir", str(tmp_path)]) == 1


def test_same_title_twice_in_one_source_kept_apart():
    a = row("Wix", "Backend Engineer", "https://gh/1", "boards")
    b = row("Wix", "Backend Engineer", "https://gh/2", "boards")
    assert len(merge.merge([a, b])) == 2


def test_name_match_only_across_sources():
    a = row("Wix", "Backend Engineer", "https://gh/1", "boards")
    b = row("Wix", "Backend Engineer", "https://gh/2", "boards")
    t = row("Wix", "Backend Engineer", "https://li/9", "techmap")
    got = merge.merge([a, b], [t])
    assert len(got) == 2 and sorted(r["source"] for r in got) == ["boards", "boards + techmap"]
