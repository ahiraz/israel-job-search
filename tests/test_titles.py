import pytest

from jobsearch.titles import NoTitlesError, TitleFilter, load_titles, normalize, parse_titles


def test_include_whole_word():
    f = TitleFilter(["data engineer"], [])
    assert f.accept("Senior Data Engineer")
    assert not f.accept("Big Data Engineering Intern Program")


def test_case_insensitive():
    assert TitleFilter(["backend engineer"], []).accept("BACKEND ENGINEER (Go)")


def test_star_wildcard():
    f = TitleFilter(["software * manager"], [])
    assert f.accept("Software Development Manager")
    assert f.accept("Software Manager")
    assert not f.accept("Software Engineer, Billing Platform Payments Team Manager x")  # >3 words between


def test_exclude_wins():
    assert not TitleFilter(["manager"], ["team lead"]).accept("Team Lead Manager")


def test_no_builtin_exclusions():
    assert TitleFilter(["lead"], []).accept("Tech Lead")
    assert TitleFilter(["manager"], []).accept("Team Lead Manager")


def test_hebrew_and_punctuation():
    assert TitleFilter(["מנהל פיתוח"], []).accept("מנהל/ת פיתוח")
    assert TitleFilter(["r&d manager"], []).accept("R&D Manager")
    assert TitleFilter(["rd manager"], []).accept("R & D Manager")
    assert TitleFilter(["senior engineer"], []).accept("Sr. / Senior Engineer")


def test_normalize():
    assert normalize("  Sr.  R&D—Manager ") == "sr rd manager"


def test_parse_sections():
    text = "[include]\nqa\n# comment\n\n[exclude]\nintern  # trailing\n"
    assert parse_titles(text) == {"include": ["qa"], "exclude": ["intern"]}


def test_parse_rejects_unknown_section():
    with pytest.raises(ValueError, match="line 1"):
        parse_titles("[broad]\nx\n")


def test_empty_include_raises(tmp_path):
    p = tmp_path / "t.txt"
    p.write_text("[include]\n\n[exclude]\nintern\n", encoding="utf-8")
    with pytest.raises(NoTitlesError, match=r"no titles in \[include\]"):
        load_titles(p)


def test_load_titles(tmp_path):
    p = tmp_path / "t.txt"
    p.write_text("[include]\nqa engineer\n[exclude]\nintern\n", encoding="utf-8")
    f = load_titles(p)
    assert f.accept("Senior QA Engineer") and not f.accept("QA Engineer Intern")
