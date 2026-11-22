"""Merge rows from several sources into one list, one row per job.

Two rows are the same job when their URLs match after normalisation (scheme
and host lowercased, query string and fragment dropped, trailing "/" removed),
or when company and title match after ``titles.normalize``.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from jobsearch.output import sort_rows
from jobsearch.titles import normalize

SOURCE_ORDER = ("boards", "techmap")


def normalize_url(url: str) -> str:
    p = urlsplit((url or "").strip())
    path = p.path.rstrip("/")
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, "", ""))


def _sources(text: str) -> list[str]:
    return [s.strip() for s in (text or "").split("+") if s.strip()]


def merge(*row_lists: list[dict]) -> list[dict]:
    merged: list[dict] = []
    by_url: dict[str, int] = {}
    by_name: dict[tuple, list[int]] = {}
    for rows in row_lists:
        for r in rows:
            ukey = normalize_url(r["url"]) if r.get("url") else None
            nkey = (normalize(r["company"]), normalize(r["title"]))
            src = set(_sources(r["source"]))
            idx = by_url.get(ukey) if ukey else None
            if idx is None:
                # A name match joins rows from different sources only: one source
                # listing the same title twice (two cities, two teams) is two jobs.
                idx = next((i for i in by_name.get(nkey, []) if not merged[i]["_src"] & src), None)
            if idx is None:
                merged.append({**r, "_src": set(src)})
                idx = len(merged) - 1
            else:
                m = merged[idx]
                m["_src"].update(_sources(r["source"]))
                if "boards" in _sources(r["source"]) and r.get("url"):
                    m["url"] = r["url"]  # the employer's own link, without tracking parameters
                if r.get("posted") and (not m["posted"] or r["posted"] < m["posted"]):
                    m["posted"] = r["posted"]
                if not m["city"] and r.get("city"):
                    m["city"] = r["city"]
            if ukey:
                by_url.setdefault(ukey, idx)
            if idx not in by_name.setdefault(nkey, []):
                by_name[nkey].append(idx)
    out = []
    for m in merged:
        src = m.pop("_src")
        m["source"] = " + ".join(sorted(src, key=lambda s: (SOURCE_ORDER.index(s)
                                                           if s in SOURCE_ORDER else 99, s)))
        out.append(m)
    return sort_rows(out)
