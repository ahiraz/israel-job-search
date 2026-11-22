"""Search every employer board for the user's titles, Israel only."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from jobsearch import adapters

WORKERS = 5
BROKEN_RUN_RATIO = 0.5


class BrokenRun(RuntimeError):
    """No board answered, or more than half failed: a network problem, not dead boards."""


def _collect(company: dict, accept) -> list[dict]:
    def keep(job: dict) -> bool:  # lets SmartRecruiters skip detail calls for the rest
        return adapters.in_israel(job) and accept(job["title"])

    rows = []
    for j in adapters.fetch_jobs(company["provider"], company["token"], keep=keep):
        if keep(j):
            rows.append({
                "company": company["name"],
                "title": j["title"],
                "city": j.get("primary_location") or j.get("location") or "",
                "posted": (j.get("posted_at") or "")[:10],
                "url": j["url"],
                "source": "boards",
            })
    return rows


def search_boards(companies: list[dict], accept, workers: int = WORKERS):
    """Returns (rows, failures) where failures is [(company name, error)].
    Raises BrokenRun if no board succeeded or more than half failed."""
    rows, failures = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_collect, c, accept): c for c in companies}
        for fut in as_completed(futures):
            c = futures[fut]
            try:
                rows += fut.result()
            except Exception as e:  # one board must never sink the run
                failures.append((c["name"], f"{type(e).__name__}: {e}"))
    if companies and (len(failures) == len(companies)
                      or len(failures) > len(companies) * BROKEN_RUN_RATIO):
        raise BrokenRun(f"{len(failures)} of {len(companies)} boards failed; check your network")
    unique: dict[str, dict] = {}
    for r in rows:
        unique.setdefault(r["url"], r)
    return list(unique.values()), sorted(failures)
