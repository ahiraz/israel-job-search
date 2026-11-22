"""Search techmap (github.com/mluggy/techmap), whose per-category CSVs list open
Israeli tech jobs, LinkedIn ones included. All 19 category files are read and
matched on title only; the user's titles carry any seniority."""

from __future__ import annotations

import csv
import io
from concurrent.futures import ThreadPoolExecutor

from jobsearch import adapters

URL = "https://raw.githubusercontent.com/mluggy/techmap/main/jobs/{name}.csv"
CATEGORIES = (
    "admin", "business", "data-science", "design", "devops", "finance", "frontend",
    "hardware", "hr", "legal", "marketing", "procurement-operations", "product",
    "project-management", "qa", "sales", "security", "software", "support",
)
WORKERS = 5


def parse_csv(text: str, accept) -> list[dict]:
    rows = []
    for r in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        title = (r.get("title") or "").strip()
        if not title or not accept(title):
            continue
        rows.append({
            "company": (r.get("company") or "").strip(),
            "title": title,
            "city": (r.get("city") or "").strip(),
            "posted": (r.get("updated") or "").strip()[:10],
            "url": (r.get("url") or "").strip(),
            "source": "techmap",
        })
    return rows


def search_techmap(accept) -> tuple[list[dict], list[str]]:
    """Returns (rows, failed category names). Rows are unique by URL."""
    def one(name: str):
        return name, parse_csv(adapters.http_get_text(URL.format(name=name)), accept)

    rows, failed = [], []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [(n, pool.submit(one, n)) for n in CATEGORIES]
        for name, fut in futures:
            try:
                rows += fut.result()[1]
            except Exception:  # one missing file must not sink the run
                failed.append(name)
    unique: dict[str, dict] = {}
    for r in rows:
        unique.setdefault(r["url"] or (r["company"], r["title"]), r)
    return list(unique.values()), failed
