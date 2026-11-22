"""Writing and showing rows: CSV, Markdown, and a terminal table.

A row is ``{company, title, city, posted, url, source}``; ``posted`` is an ISO
date (YYYY-MM-DD) or "".
"""

from __future__ import annotations

import csv
from pathlib import Path

FIELDS = ("company", "title", "city", "posted", "url", "source")


def sort_rows(rows: list[dict]) -> list[dict]:
    """Newest first; undated last; ties by company then title."""
    dated = sorted((r for r in rows if r.get("posted")),
                   key=lambda r: (r["company"].lower(), r["title"].lower()))
    dated.sort(key=lambda r: r["posted"], reverse=True)
    undated = sorted((r for r in rows if not r.get("posted")),
                     key=lambda r: (r["company"].lower(), r["title"].lower()))
    return dated + undated


def _atomic_write(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="")
    tmp.replace(path)


def write_csv(rows: list[dict], path: Path) -> None:
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in FIELDS})
    _atomic_write(path, buf.getvalue())


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return [{k: row.get(k) or "" for k in FIELDS} for row in csv.DictReader(f)]


def _md(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ")


def write_markdown(rows: list[dict], path: Path, heading: str) -> None:
    rows = sort_rows(rows)
    companies = len({r["company"] for r in rows})
    lines = [f"# {heading}", "", f"{len(rows)} jobs · {companies} companies", "",
             "| Company | Title | City | Posted | Found in | Link |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {_md(r['company'])} | {_md(r['title'])} | {_md(r['city'])} | "
                     f"{r['posted'] or '—'} | {r['source']} | [apply]({r['url']}) |")
    _atomic_write(path, "\n".join(lines) + "\n")


def _cut(text: str, width: int) -> str:
    text = (text or "").replace("\n", " ")
    return text if len(text) <= width else text[: width - 1] + "…"


def table(rows: list[dict], limit: int = 50) -> str:
    rows = sort_rows(rows)
    out = [f"{'Company':22} {'Title':44} {'City':18} {'Posted':10}  Link"]
    for r in rows[:limit]:
        out.append(f"{_cut(r['company'], 22):22} {_cut(r['title'], 44):44} "
                   f"{_cut(r['city'], 18):18} {r['posted'] or '—':10}  {r['url']}")
    if len(rows) > limit:
        out.append(f"… and {len(rows) - limit} more (see the saved file)")
    return "\n".join(out)
