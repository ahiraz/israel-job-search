# jobsearch/adapters.py
"""Read employers' public ATS job-board JSON feeds.

Each employer's own careers page loads its job list from one of these
unauthenticated endpoints; we read the same thing. Every adapter returns jobs
in one shape:

    {title, location, primary_location, description, url, department, posted_at, external_id}

`location` is everything the board lists (shown to the user); `primary_location`
is the one the employer lists the job under, which is what decides whether it
is "in Israel" (see in_israel). Boards like Greenhouse list a job under Paris
and name Tel Aviv as one of ten alternative offices; that is a Paris job.

`description` is plain text, capped at MAX_DESC chars (it is sent to the LLM
matcher, so unbounded text is unbounded cost).

Ported from github.com/baldiga/jobsworm packages/adapters (MIT), which has the
response shapes verified against live boards.

The optional `keep(job) -> bool` argument lets a caller drop jobs *before* an
adapter spends extra requests on them. Only SmartRecruiters needs it (its list
has no descriptions, so the body costs one request per job); the others ignore
it because their list already carries the body.
"""

import html
import json
import os
import re
import ssl
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from typing import Callable, Optional
from urllib.parse import quote, urlsplit

USER_AGENT = "IsraelJobSearch/1.0 (+https://github.com/ahiraz/israel-job-search; reads public job boards)"
MAX_DESC = 8000
TIMEOUT = 30
HOST_DELAY = 0.35  # minimum gap between two requests to the same host, seconds

Job = dict
Keep = Optional[Callable[[Job], bool]]


# ── HTTP ────────────────────────────────────────────────────────────────────

_host_lock = threading.Lock()
_host_next: dict[str, float] = {}


def _throttle(url: str) -> None:
    """Block until at least HOST_DELAY has passed since the last request to this
    host, across threads. ~280 companies spread over ~6 hosts, so Comeet (172
    of them) is the one that actually waits."""
    host = urlsplit(url).netloc
    with _host_lock:
        now = time.monotonic()
        start = max(now, _host_next.get(host, 0.0))
        _host_next[host] = start + HOST_DELAY
    if start > now:
        time.sleep(start - now)


# Where the OS keeps its CA certificates. Used when Python's own store is empty,
# as with the python.org macOS installer before "Install Certificates" is run.
_CA_BUNDLES = (
    "/etc/ssl/cert.pem",                    # macOS, Alpine
    "/etc/ssl/certs/ca-certificates.crt",   # Debian, Ubuntu
    "/etc/pki/tls/certs/ca-bundle.crt",     # Fedora, RHEL
)


def _ssl_context():
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get("x509_ca", 0) == 0:
        for path in _CA_BUNDLES:
            if os.path.exists(path):
                ctx.load_verify_locations(cafile=path)
                break
    return ctx


_SSL = None


def _get(url: str, accept: str, retries: int = 2) -> str:
    """GET `url` and return the decoded body. Retries 429/5xx honouring
    Retry-After, and network errors with backoff."""
    global _SSL
    if _SSL is None:
        _SSL = _ssl_context()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    for attempt in range(retries + 1):
        _throttle(url)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_SSL) as resp:
                return resp.read().decode("utf-8-sig")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                wait = e.headers.get("Retry-After", "")
                time.sleep(min(30, int(wait)) if wait.isdigit() else 2 ** (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            raise


def http_get_json(url: str, retries: int = 2):
    """GET `url` and parse JSON. Module level so tests can patch it."""
    return json.loads(_get(url, "application/json", retries))


def http_get_text(url: str, retries: int = 2) -> str:
    """GET `url` as text (CSV, HTML), same throttle and User-Agent."""
    return _get(url, "text/html,text/csv,*/*;q=0.8", retries)


# ── Text helpers ────────────────────────────────────────────────────────────

_BLOCK_END = re.compile(r"</(?:p|div|li|h[1-6]|tr)>|<br\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")


def strip_html(markup: str) -> str:
    """HTML -> readable plain text (entities decoded, block ends -> newlines)."""
    if not markup:
        return ""
    text = _BLOCK_END.sub("\n", markup)
    text = html.unescape(_TAG.sub("", text))
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _clip(text: str) -> str:
    return text[:MAX_DESC]


def _join_unique(parts) -> str:
    seen, out = set(), []
    for p in parts:
        if isinstance(p, str) and p.strip() and p.strip().lower() not in seen:
            seen.add(p.strip().lower())
            out.append(p.strip())
    return ", ".join(out)


def _job(external_id, title, location, description, url, department=None, posted_at=None,
         primary=None) -> Job:
    return {
        "primary_location": location or "" if primary is None else primary,
        "external_id": str(external_id),
        "title": (title or "").strip(),
        "location": location or "",
        "description": _clip(description or ""),
        "url": url or "",
        "department": department or "",
        "posted_at": posted_at or "",
    }


# ── Israel detection (ported from jobsworm scripts/seed/verify_ats.py) ──────

_IL_PATTERNS = [
    "israel", "ישראל", "isr",
    "tel aviv", "tel-aviv", "telaviv", "תל אביב", "tlv",
    "herzliya", "herzeliya", "hertzliya", "הרצליה",
    "ra'anana", "raanana", "ra anana", "רעננה",
    "petah tikva", "petach tikva", "petah-tikva", "petax tikva", "פתח תקווה",
    "haifa", "חיפה", "jerusalem", "ירושלים", "netanya", "nathanya", "נתניה",
    "beer sheva", "be'er sheva", "beersheba", "beer-sheva", "באר שבע",
    "yokneam", "yoqneam", "יקנעם", "caesarea", "קיסריה", "rehovot", "רחובות",
    "ramat gan", "ramat-gan", "רמת גן", "givatayim", "גבעתיים",
    "hod hasharon", "הוד השרון", "kfar saba", "kefar sava", "כפר סבא",
    "airport city", "modiin", "modi'in", "מודיעין",
    "rosh haayin", "rosh ha'ayin", "rosh ha ayin", "ראש העין",
    "holon", "חולון", "bnei brak", "בני ברק", "or yehuda", "אור יהודה",
    "ness ziona", "nes ziona", "נס ציונה", "rishon", "ראשון לציון",
    "lod", "ashdod", "אשדוד", "ashkelon", "אשקלון", "migdal haemek",
    "kiryat gat", "kiryat ono", "hasharon", "sderot", "afula", "tirat carmel",
    "yavne", "יבנה", "givat shmuel", "azrieli",
]
# word-bounded, so 'lod' does not match 'Lodz' and 'isr' does not match 'Isreal-less' words
_IL_RX = [re.compile(r"(?<!\w)" + re.escape(p) + r"(?!\w)", re.I) for p in _IL_PATTERNS]
_IL_CODES = {"il", "isr", "israel"}


def is_israeli(text: Optional[str]) -> bool:
    t = unicodedata.normalize("NFKC", text or "").strip().lower()
    if not t:
        return False
    if t in _IL_CODES:
        return True
    return any(rx.search(t) for rx in _IL_RX)


# A primary location that says nothing about *where* ("Remote", "Hybrid", "Multiple
# locations"...) cannot settle the question; fall back to everything listed.
_VAGUE = re.compile(r"^(?:remote|hybrid|on[- ]?site|anywhere|worldwide|global|multiple|various|flexible|[\W_])*"
                    r"(?:locations?|offices?)?$", re.I)


def in_israel(job: Job) -> bool:
    """Is this job in Israel? Decided by the job's primary location. Only when that
    is empty or vague does the full list of offices count, so a Paris job that
    also names Tel Aviv among ten offices is not an Israeli job."""
    # Some boards put a list in one field ("Bangalore, India; Remote, Canada; Remote,
    # Israel"): the first entry is the one the job is listed under.
    primary = (job.get("primary_location") or "").split(";")[0].strip()
    if primary and not _VAGUE.match(primary):
        return is_israeli(primary)
    return is_israeli(job.get("location"))


def _country(code: Optional[str]) -> str:
    return "Israel" if (code or "").strip().lower() in _IL_CODES else ""


# ── Providers ───────────────────────────────────────────────────────────────

def greenhouse(token: str, keep: Keep = None) -> list[Job]:
    data = http_get_json(f"https://boards-api.greenhouse.io/v1/boards/{quote(token)}/jobs?content=true")
    out = []
    for j in (data.get("jobs") if isinstance(data, dict) else None) or []:
        loc = _join_unique([(j.get("location") or {}).get("name")] + [(o or {}).get("name") for o in j.get("offices") or []])
        out.append(_job(
            j.get("id"), j.get("title"), loc,
            strip_html(html.unescape(j.get("content") or "")),  # content arrives entity-escaped
            j.get("absolute_url") or f"https://job-boards.greenhouse.io/{token}/jobs/{j.get('id')}",
            ((j.get("departments") or [{}])[0] or {}).get("name"),
            j.get("first_published") or j.get("updated_at"),
            primary=(j.get("location") or {}).get("name") or "",
        ))
    return out


def lever(token: str, keep: Keep = None) -> list[Job]:
    data = http_get_json(f"https://api.lever.co/v0/postings/{quote(token)}?mode=json")
    out = []
    for p in data if isinstance(data, list) else []:
        cats = p.get("categories") or {}
        loc = _join_unique([cats.get("location"), *(cats.get("allLocations") or []), _country(p.get("country"))])
        body = [p.get("descriptionPlain") or strip_html(p.get("description") or "")]
        for lst in p.get("lists") or []:
            body += [lst.get("text") or "", strip_html(lst.get("content") or "")]
        body.append(strip_html(p.get("additional") or ""))
        created = p.get("createdAt")
        out.append(_job(
            p.get("id"), p.get("text"), loc, "\n".join(b for b in body if b),
            p.get("hostedUrl") or p.get("applyUrl") or f"https://jobs.lever.co/{token}/{p.get('id')}",
            cats.get("department") or cats.get("team"),
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(created / 1000)) if isinstance(created, (int, float)) else "",
            primary=_join_unique([cats.get("location"), _country(p.get("country"))]),
        ))
    return out


def ashby(token: str, keep: Keep = None) -> list[Job]:
    data = http_get_json(f"https://api.ashbyhq.com/posting-api/job-board/{quote(token)}")
    out = []
    for j in (data.get("jobs") if isinstance(data, dict) else None) or []:
        if j.get("isListed") is False:
            continue
        loc = _join_unique([j.get("location"), *((s or {}).get("location") for s in j.get("secondaryLocations") or [])])
        out.append(_job(
            j.get("id"), j.get("title"), loc,
            j.get("descriptionPlain") or strip_html(j.get("descriptionHtml") or ""),
            j.get("jobUrl") or j.get("applyUrl") or f"https://jobs.ashbyhq.com/{token}/{j.get('id')}",
            j.get("department") or j.get("team"), j.get("publishedAt") or j.get("updatedAt"),
            primary=j.get("location") or "",
        ))
    return out


def comeet(stored: str, keep: Keep = None) -> list[Job]:
    """`stored` is "uid::token" — Comeet needs both. details=true is mandatory:
    without it the payload carries no description at all."""
    uid, sep, tok = stored.partition("::")
    if not sep:
        raise ValueError('Comeet token must be stored as "uid::token"')
    data = http_get_json(
        f"https://www.comeet.co/careers-api/2.0/company/{quote(uid)}/positions?token={quote(tok)}&details=true")
    positions = data if isinstance(data, list) else (data.get("positions") or [])
    out = []
    for p in positions:
        if not (p.get("uid") and p.get("name")):
            continue
        loc = p.get("location") or {}
        location = _join_unique([loc.get("name"), loc.get("city"), loc.get("state"), _country(loc.get("country")),
                                 "Remote" if loc.get("is_remote") else "", p.get("workplace_type")])
        body = "\n".join(
            (f"{d['name']}\n" if d.get("name") else "") + strip_html(d.get("value") or "")
            for d in p.get("details") or [] if d.get("value"))
        url = p.get("url_comeet_hosted_page") or p.get("url_active_page") or ""
        if url:
            out.append(_job(p["uid"], p["name"], location, body, url, p.get("department"), p.get("time_updated")))
    return out


def recruitee(token: str, keep: Keep = None) -> list[Job]:
    data = http_get_json(f"https://{quote(token)}.recruitee.com/api/offers/")
    out = []
    for o in (data.get("offers") if isinstance(data, dict) else None) or []:
        if not (o.get("id") and o.get("title")):
            continue
        loc = _join_unique([o.get("location"), o.get("city"), o.get("state_name"), _country(o.get("country_code")),
                            "Remote" if o.get("remote") else ""])
        body = strip_html(o.get("description") or "") + "\n" + strip_html(o.get("requirements") or "")
        out.append(_job(
            o["id"], o["title"], loc, body.strip(),
            o.get("careers_apply_url") or o.get("careers_url") or f"https://{token}.recruitee.com/o/{o.get('slug') or o['id']}",
            o.get("department"), o.get("published_at") or o.get("created_at")))
    return out


_SR_PAGE = 100
_SR_MAX = 400


def smartrecruiters(token: str, keep: Keep = None) -> list[Job]:
    """The list has no description; the body is one request per posting. Only
    postings that pass `keep` get that request."""
    base = f"https://api.smartrecruiters.com/v1/companies/{quote(token)}/postings"
    listed = []
    for offset in range(0, _SR_MAX, _SR_PAGE):
        page = http_get_json(f"{base}?limit={_SR_PAGE}&offset={offset}")
        batch = (page.get("content") if isinstance(page, dict) else None) or []
        listed += batch
        if len(batch) < _SR_PAGE:
            break

    out = []
    for p in listed:
        loc = p.get("location") or {}
        location = loc.get("fullLocation") or _join_unique([loc.get("city"), loc.get("region"), loc.get("country")])
        if loc.get("remote"):
            location += ", Remote"
        job = _job(p.get("id"), p.get("name"), location, "",
                   f"https://jobs.smartrecruiters.com/{token}/{p.get('id')}",
                   (p.get("department") or {}).get("label"), p.get("releasedDate"))
        if keep is not None and not keep(job):
            continue
        try:
            sec = ((http_get_json(f"{base}/{quote(str(p['id']))}").get("jobAd") or {}).get("sections")) or {}
            job["description"] = _clip("\n".join(
                (f"{s['title']}\n" if s.get("title") else "") + strip_html(s.get("text") or "")
                for s in (sec.get(k) for k in ("companyDescription", "jobDescription", "qualifications", "additionalInformation"))
                if s and s.get("text")))
        except Exception:
            pass  # one unavailable posting must not fail the company
        out.append(job)
    return out


PROVIDERS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "comeet": comeet,
    "recruitee": recruitee,
    "smartrecruiters": smartrecruiters,
}


def fetch_jobs(provider: str, token: str, keep: Keep = None) -> list[Job]:
    """Fetch every posting on one employer's board. Raises on a failed fetch or
    an unknown provider; the caller decides what a failure means."""
    try:
        fn = PROVIDERS[provider]
    except KeyError:
        raise ValueError(f"no adapter for provider {provider!r}") from None
    return fn(token, keep)
