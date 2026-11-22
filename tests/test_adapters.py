"""Adapter tests: http_get_json is patched with trimmed fixtures of each
provider's real response shape (see jobsworm packages/adapters); no network."""

import pytest

from jobsearch import adapters as a


def patch_http(monkeypatch, routes):
    """routes: {substring of url: payload}. First match wins; records URLs."""
    calls = []

    def fake(url, retries=2):
        calls.append(url)
        for needle, payload in routes.items():
            if needle in url:
                return payload
        raise AssertionError(f"unexpected URL {url}")

    monkeypatch.setattr(a, "http_get_json", fake)
    return calls


def test_strip_html_blocks_entities_and_cap():
    out = a.strip_html("<p>Lead &amp; grow</p><ul><li>One</li><li>Two</li></ul>End<br>Last")
    assert out == "Lead & grow\nOne\nTwo\nEnd\nLast"
    assert a.strip_html("") == ""


def test_greenhouse_unescapes_content_and_joins_locations(monkeypatch):
    patch_http(monkeypatch, {"boards-api.greenhouse.io/v1/boards/acme/jobs": {"jobs": [{
        "id": 7, "title": " Head of Data ", "absolute_url": "https://x/7",
        "content": "&lt;p&gt;Lead the &amp;amp; team&lt;/p&gt;",
        "location": {"name": "Tel Aviv"}, "offices": [{"name": "Tel Aviv"}, {"name": "Israel"}],
        "departments": [{"name": "Data"}], "first_published": "2026-10-01T00:00:00Z"}]}})
    [j] = a.greenhouse("acme")
    assert j["title"] == "Head of Data"
    assert j["description"] == "Lead the & team"
    assert j["location"] == "Tel Aviv, Israel"
    assert (j["url"], j["department"], j["external_id"]) == ("https://x/7", "Data", "7")


def test_lever_builds_body_from_lists_and_country(monkeypatch):
    patch_http(monkeypatch, {"api.lever.co/v0/postings/acme": [{
        "id": "abc", "text": "VP R&D", "hostedUrl": "https://jobs.lever.co/acme/abc", "country": "IL",
        "descriptionPlain": "About", "createdAt": 1_700_000_000_000,
        "lists": [{"text": "Requirements", "content": "<li>10y</li>"}],
        "categories": {"location": "Herzliya", "allLocations": ["Herzliya"], "department": "R&D"}}]})
    [j] = a.lever("acme")
    assert j["location"] == "Herzliya, Israel"
    assert "Requirements" in j["description"] and "10y" in j["description"]
    assert j["posted_at"].startswith("2023-11-14")


def test_ashby_skips_unlisted(monkeypatch):
    patch_http(monkeypatch, {"posting-api/job-board/acme": {"jobs": [
        {"id": "1", "title": "Director", "isListed": True, "location": "Tel Aviv", "descriptionPlain": "d", "jobUrl": "u"},
        {"id": "2", "title": "Hidden", "isListed": False}]}})
    assert [j["title"] for j in a.ashby("acme")] == ["Director"]


def test_comeet_needs_both_halves_and_details(monkeypatch):
    calls = patch_http(monkeypatch, {"careers-api/2.0/company/15.007/positions": [{
        "uid": "AB.D67", "name": "Engineering Manager", "department": "R&D", "workplace_type": "Hybrid",
        "location": {"name": "Tel Aviv", "city": "Tel Aviv", "country": "IL"},
        "url_comeet_hosted_page": "https://www.comeet.com/jobs/x/15.007/em/AB.D67",
        "details": [{"name": "Description", "value": "<p>Run it</p>"}]},
        {"uid": "no.url", "name": "No link"}]})
    [j] = a.comeet("15.007::ABCDEF")
    assert "details=true" in calls[0] and "token=ABCDEF" in calls[0]
    assert j["location"] == "Tel Aviv, Israel, Hybrid"
    assert j["description"] == "Description\nRun it"
    with pytest.raises(ValueError, match="uid::token"):
        a.comeet("justone")


def test_recruitee(monkeypatch):
    patch_http(monkeypatch, {"acme.recruitee.com/api/offers": {"offers": [{
        "id": 5, "title": "Head of Eng", "location": "Haifa", "country_code": "IL", "remote": False,
        "description": "<p>Hi</p>", "requirements": "<p>Req</p>", "careers_url": "https://acme.recruitee.com/o/5"}]}})
    [j] = a.recruitee("acme")
    assert j["location"] == "Haifa, Israel" and j["url"].endswith("/o/5")


def test_smartrecruiters_only_fetches_details_for_kept_jobs(monkeypatch):
    calls = patch_http(monkeypatch, {
        "/postings/1": {"jobAd": {"sections": {"jobDescription": {"title": "Role", "text": "<p>Lead</p>"}}}},
        "/postings?limit": {"content": [
            {"id": "1", "name": "Director of Engineering", "location": {"fullLocation": "Tel Aviv, Israel"}},
            {"id": "2", "name": "Backend Engineer", "location": {"fullLocation": "Tel Aviv, Israel"}}]},
    })
    jobs = a.smartrecruiters("acme", keep=lambda j: "director" in j["title"].lower())
    assert [j["title"] for j in jobs] == ["Director of Engineering"]
    assert jobs[0]["description"] == "Role\nLead"
    assert not any("/postings/2" in c for c in calls)  # the dropped job cost no request


def test_smartrecruiters_detail_failure_keeps_the_job(monkeypatch):
    def fake(url, retries=2):
        if "/postings/1" in url:
            raise OSError("boom")
        return {"content": [{"id": "1", "name": "VP", "location": {"city": "Tel Aviv", "country": "il"}}]}
    monkeypatch.setattr(a, "http_get_json", fake)
    [j] = a.smartrecruiters("acme")
    assert j["title"] == "VP" and j["description"] == ""


def test_description_is_capped(monkeypatch):
    patch_http(monkeypatch, {"posting-api": {"jobs": [{"id": "1", "title": "t", "descriptionPlain": "x" * 50_000}]}})
    assert len(a.ashby("acme")[0]["description"]) == a.MAX_DESC


def test_unknown_provider():
    with pytest.raises(ValueError, match="no adapter"):
        a.fetch_jobs("workday", "x")


@pytest.mark.parametrize("text,expected", [
    ("Tel Aviv, Israel", True), ("תל אביב", True), ("Herzliya", True), ("IL", True), ("Ra'anana", True),
    ("Lodz, Poland", False), ("London", False), ("Remote", False), ("", False), (None, False),
])
def test_is_israeli(text, expected):
    assert a.is_israeli(text) is expected


# ── in_israel: the primary location decides, not the list of alternative offices ──

DATADOG_LIKE = {"jobs": [{
    "id": 8051068, "title": "Manager I, Engineering - Source Code Integration",
    "absolute_url": "https://careers.datadoghq.com/detail/8051068/?gh_jid=8051068", "content": "",
    "location": {"name": "Paris, France"},
    "offices": [{"name": "Bordeaux"}, {"name": "Paris"}, {"name": "Remote - France"}, {"name": "Tel Aviv"}]}]}


def test_job_listed_in_paris_with_tel_aviv_as_one_office_is_not_in_israel(monkeypatch):
    patch_http(monkeypatch, {"boards-api.greenhouse.io/v1/boards/datadog": DATADOG_LIKE})
    [j] = a.greenhouse("datadog")
    assert j["primary_location"] == "Paris, France"
    assert "Tel Aviv" in j["location"]          # still shown to the user in full
    assert a.is_israeli(j["location"])          # the old test would have kept it
    assert not a.in_israel(j)                   # the fix


def test_job_listed_in_tel_aviv_is_in_israel_even_with_other_offices(monkeypatch):
    patch_http(monkeypatch, {"boards-api.greenhouse.io/v1/boards/datadog": {"jobs": [{
        "id": 1, "title": "Director, Engineering", "location": {"name": "Tel Aviv, Israel"},
        "offices": [{"name": "New York"}, {"name": "Paris"}]}]}})
    [j] = a.greenhouse("datadog")
    assert a.in_israel(j)


def test_lever_and_ashby_use_primary_location_too(monkeypatch):
    patch_http(monkeypatch, {
        "api.lever.co/v0/postings/acme": [{"id": "1", "text": "VP", "hostedUrl": "u",
            "categories": {"location": "London", "allLocations": ["London", "Tel Aviv"]}}],
        "posting-api/job-board/acme": {"jobs": [{"id": "2", "title": "VP", "jobUrl": "u", "location": "Berlin",
            "secondaryLocations": [{"location": "Tel Aviv"}]}]}})
    assert not a.in_israel(a.lever("acme")[0])
    assert not a.in_israel(a.ashby("acme")[0])


@pytest.mark.parametrize("primary,full,expected", [
    ("Tel Aviv, Israel", "Tel Aviv, Israel, Paris", True),
    ("Paris, France", "Paris, France, Tel Aviv", False),
    ("Remote", "Remote, Tel Aviv", True),            # vague primary: look at everything
    ("Remote", "Remote, London", False),
    ("Multiple Locations", "Multiple Locations, Haifa", True),
    ("", "Tel Aviv", True),
    ("", "", False),
    ("Bangalore, India; Remote, Canada; Remote, Israel", "Bangalore, India; Remote, Israel", False),  # GitLab-style list
    ("Tel Aviv, Israel; Remote, Canada", "Tel Aviv, Israel; Remote, Canada", True),
    ("Remote; Tel Aviv", "Remote; Tel Aviv", True),
])
def test_in_israel(primary, full, expected):
    assert a.in_israel({"primary_location": primary, "location": full}) is expected


def test_user_agent_points_at_repo():
    assert a.USER_AGENT.startswith("IsraelJobSearch/1.0")


def test_http_get_text_sends_ua_and_decodes(monkeypatch):
    seen = {}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *e): return False
        def read(self): return "﻿שלום,x".encode("utf-8")

    def fake_urlopen(req, timeout, context=None):
        seen["ua"] = req.get_header("User-agent")
        return Resp()

    monkeypatch.setattr(a.urllib.request, "urlopen", fake_urlopen)
    assert a.http_get_text("https://example.com/x.csv") == "שלום,x"
    assert seen["ua"] == a.USER_AGENT


def test_ssl_context_falls_back_to_system_bundle(monkeypatch, tmp_path):
    import ssl
    loaded = []

    class Ctx:
        def cert_store_stats(self): return {"x509_ca": 0}
        def load_verify_locations(self, cafile): loaded.append(cafile)

    monkeypatch.setattr(ssl, "create_default_context", lambda: Ctx())
    bundle = tmp_path / "cert.pem"
    bundle.write_text("x")
    monkeypatch.setattr(a, "_CA_BUNDLES", (str(tmp_path / "missing.pem"), str(bundle)))
    a._ssl_context()
    assert loaded == [str(bundle)]


def test_ssl_context_keeps_default_when_it_has_certs(monkeypatch):
    import ssl

    class Ctx:
        def cert_store_stats(self): return {"x509_ca": 120}
        def load_verify_locations(self, cafile): raise AssertionError("should not load")

    monkeypatch.setattr(ssl, "create_default_context", lambda: Ctx())
    a._ssl_context()
