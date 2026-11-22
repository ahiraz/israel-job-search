from jobsearch import output

ROWS = [
    {"company": "A", "title": "Old", "city": "Haifa", "posted": "2026-01-01", "url": "u1", "source": "boards"},
    {"company": "B", "title": "Undated", "city": "", "posted": "", "url": "u2", "source": "techmap"},
    {"company": "C, Ltd", "title": "New \"x\"", "city": "תל אביב", "posted": "2026-11-01", "url": "u3", "source": "boards"},
]


def test_csv_round_trip(tmp_path):
    p = tmp_path / "a" / "x.csv"
    output.write_csv(ROWS, p)
    assert output.read_csv(p) == ROWS


def test_sort_newest_first_undated_last():
    assert [r["title"] for r in output.sort_rows(ROWS)] == ['New "x"', "Old", "Undated"]


def test_table_sorted_and_limited():
    t = output.table(ROWS, limit=2)
    assert t.index('New "x"') < t.index("Old")
    assert "Undated" not in t and "1 more" in t


def test_markdown(tmp_path):
    p = tmp_path / "x.md"
    output.write_markdown(ROWS, p, heading="Backend Engineer")
    md = p.read_text(encoding="utf-8")
    assert md.startswith("# Backend Engineer")
    assert "| Company | Title | City | Posted | Found in | Link |" in md
    assert "[apply](u3)" in md
