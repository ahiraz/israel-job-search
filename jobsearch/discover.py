"""Find employer job boards we don't know yet, from a list of URLs.

The update-companies skill runs web searches (``site:job-boards.greenhouse.io
"Tel Aviv"`` and friends) and hands every result URL to this module, which:

1. recognises ATS board URLs and pulls out the board token
   (fingerprints ported from jobsworm ``scripts/seed/detect_ats.py``),
2. drops boards already in the shipped or personal company list,
3. fetches each remaining board and keeps it only if it has at least one job
   in Israel (the same rule jobsworm used before adding a company).
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

from jobsearch import adapters
from jobsearch.companies import known_boards

WORKERS = 5

FINGERPRINTS: list[tuple[str, re.Pattern]] = [
    ("greenhouse", re.compile(r"greenhouse\.io/embed/job_board\?for=([A-Za-z0-9_.\-]{2,40})")),
    ("greenhouse", re.compile(
        r"(?:job-)?boards(?:-api)?(?:\.eu)?\.greenhouse\.io/(?:v1/boards/)?([A-Za-z0-9_.\-]{2,40})")),
    ("lever", re.compile(r"(?:jobs\.lever\.co|api\.lever\.co/v0/postings)/([A-Za-z0-9_.\-]{2,40})")),
    ("ashby", re.compile(
        r"(?:jobs\.ashbyhq\.com|api\.ashbyhq\.com/posting-api/job-board)/([A-Za-z0-9_.\-]{2,40})")),
    ("smartrecruiters", re.compile(
        r"(?:jobs\.smartrecruiters\.com|api\.smartrecruiters\.com/v1/companies)/([A-Za-z0-9_.\-]{2,40})")),
    ("recruitee", re.compile(r"//([A-Za-z0-9_\-]{2,40})\.recruitee\.com")),
]
RX_COMEET_HOSTED = re.compile(r"comeet\.com/jobs/([A-Za-z0-9_\-.]+)/([0-9A-Fa-f]{2}\.[0-9A-Fa-f]{3})")
RX_COMEET_API = re.compile(
    r"careers-api/2\.0/company/([0-9A-Za-z.]+)/positions[^\"'<>\s]*token=([0-9A-Za-z.]+)")
RX_COMEET_TOK = re.compile(
    r"""(?:token|comeet_token|data-token)['"]?\s*[:=]\s*['"]([0-9A-Za-z.]{20,45})['"]""")

JUNK = {"embed", "job_board", "jobs", "v1", "boards", "api", "www", "posting-api",
        "job-board", "accounts", "widget", "companies", "postings", "static",
        "assets", "css", "js", "images", "img", "en", "he", "careers", "search",
        "for", "token", "index", "app", "cdn", "s", "u", "e", "public"}

CAREERS = {
    "greenhouse": "https://job-boards.greenhouse.io/{t}",
    "lever": "https://jobs.lever.co/{t}",
    "ashby": "https://jobs.ashbyhq.com/{t}",
    "smartrecruiters": "https://jobs.smartrecruiters.com/{t}",
    "recruitee": "https://{t}.recruitee.com",
}


def _clean(tok: str) -> str | None:
    t = tok.strip().strip(".-_").lower()
    if not t or t in JUNK or len(t) < 2 or len(t) > 40:
        return None
    if t.endswith((".js", ".css", ".png", ".svg", ".json", ".html")):
        return None
    return t


def extract_boards(urls: list[str]) -> list[tuple[str, str]]:
    """Board (provider, token) pairs found in `urls`, in first-seen order. Comeet
    boards come out as ("comeet", "slug/UID"): the API token still has to be read
    from the hosted page (resolve_comeet)."""
    out: list[tuple[str, str]] = []
    for url in urls:
        m = RX_COMEET_HOSTED.search(url)
        if m:
            key = ("comeet", f"{m.group(1).lower()}/{m.group(2).upper()}")
            if key not in out:
                out.append(key)
            continue
        for prov, rx in FINGERPRINTS:
            m = rx.search(url)
            if m:
                t = _clean(m.group(1))
                if t and (prov, t) not in out:
                    out.append((prov, t))
                break
    return out


def resolve_comeet(slug: str, uid: str) -> str | None:
    """Read the Comeet hosted board page and return "UID::token", or None."""
    page = adapters.http_get_text(f"https://www.comeet.com/jobs/{slug}/{uid}")
    m = RX_COMEET_API.search(page)
    if m:
        return f"{m.group(1)}::{m.group(2)}"
    m = RX_COMEET_TOK.search(page)
    return f"{uid}::{m.group(1)}" if m else None


def board_name(provider: str, token: str) -> str:
    """The employer's display name where the ATS offers one; otherwise the token."""
    if provider == "greenhouse":
        try:
            return adapters.http_get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}")["name"]
        except Exception:
            pass
    return token.split("::")[0] if provider != "comeet" else token


def careers_url(provider: str, token: str, slug: str = "") -> str:
    if provider == "comeet":
        return f"https://www.comeet.com/jobs/{slug}/{token.split('::')[0]}"
    return CAREERS[provider].format(t=token)


def verify(provider: str, token: str, slug: str = "", name: str = "") -> dict | None:
    """The board as a company entry if it has at least one job in Israel, else None.
    Raises if the board cannot be fetched."""
    jobs = adapters.fetch_jobs(provider, token)
    n = sum(1 for j in jobs if adapters.in_israel(j))
    if not n:
        return None
    return {"name": name or board_name(provider, token), "domain": "", "provider": provider,
            "token": token, "careers_url": careers_url(provider, token, slug), "jobs_israel": n}


def _key(provider: str, token: str) -> tuple[str, str]:
    """Comeet boards are identified by company UID; others by lowercase token."""
    if provider == "comeet":
        return provider, token.split("::")[0].split("/")[-1].upper()
    return provider, token.lower()


def discover(urls: list[str]) -> dict:
    """{"new": [company entries], "skipped": [{"board", "reason"}]}"""
    known = {_key(p, t) for p, t in known_boards()}
    todo, skipped = [], []
    for prov, tok in extract_boards(urls):
        if _key(prov, tok) in known:
            skipped.append({"board": f"{prov}/{tok}", "reason": "known"})
        else:
            todo.append((prov, tok))

    def check(prov: str, tok: str):
        try:
            if prov == "comeet":
                slug, uid = tok.split("/")
                full = resolve_comeet(slug, uid)
                if not full:
                    return None, "no comeet token on page"
                found = verify(prov, full, slug=slug, name=slug)
            else:
                found = verify(prov, tok)
        except Exception:
            return None, "fetch failed"
        return (found, None) if found else (None, "no israeli jobs")

    new = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = list(pool.map(lambda b: check(*b), todo))
    for (prov, tok), (found, reason) in zip(todo, results):
        if found:
            new.append(found)
        else:
            skipped.append({"board": f"{prov}/{tok}", "reason": reason})
    return {"new": new, "skipped": skipped}
