"""Command line used by the skills: boards | techmap | merge | discover.

Exit codes: 0 ok, 1 the run as a whole failed (previous output kept),
2 bad input (titles file, companies file, arguments).
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

from jobsearch import boards as boards_mod
from jobsearch import discover as discover_mod
from jobsearch import merge as merge_mod
from jobsearch import output, techmap
from jobsearch.companies import CompanyFileError, add_user_companies, load_companies, user_file
from jobsearch.titles import load_titles


def _err(msg: str) -> None:
    print(msg, file=sys.stderr)


def _load_filter(path: str):
    try:
        return load_titles(Path(path))
    except FileNotFoundError:
        _err(f"titles file not found: {path} (run the job-titles skill first)")
    except ValueError as e:  # NoTitlesError is a ValueError
        _err(str(e))
    return None


def cmd_boards(args) -> int:
    flt = _load_filter(args.titles)
    if flt is None:
        return 2
    try:
        companies = load_companies()
    except CompanyFileError as e:
        _err(str(e))
        return 2
    try:
        rows, failures = boards_mod.search_boards(companies, flt.accept)
    except boards_mod.BrokenRun as e:
        _err(f"Board search failed: {e}")
        return 1
    for name, error in failures:
        _err(f"  failed: {name}: {error}")
    output.write_csv(rows, Path(args.out))
    print(f"Searched {len(companies)} company boards ({len(failures)} failed)")
    print(f"Found {len(rows)} jobs in Israel")
    print(output.table(rows))
    print(f"Saved → {args.out}")
    return 0


def cmd_techmap(args) -> int:
    flt = _load_filter(args.titles)
    if flt is None:
        return 2
    rows, failed = techmap.search_techmap(flt.accept)
    if len(failed) == len(techmap.CATEGORIES):
        _err("Techmap search failed: no category file could be downloaded; check your network")
        return 1
    for name in failed:
        _err(f"  failed: techmap {name}.csv")
    output.write_csv(rows, Path(args.out))
    print(f"Read {len(techmap.CATEGORIES) - len(failed)} techmap categories ({len(failed)} failed)")
    print(f"Found {len(rows)} jobs in techmap (LinkedIn via techmap)")
    print(output.table(rows))
    print(f"Saved → {args.out}")
    return 0


def cmd_merge(args) -> int:
    lists = []
    for p in args.inputs:
        try:
            lists.append(output.read_csv(Path(p)))
        except FileNotFoundError:
            _err(f"  skipped (not found): {p}")
    if not lists:
        _err("Nothing to merge: none of the input files exist")
        return 1
    total = sum(len(rows) for rows in lists)
    rows = merge_mod.merge(*lists)
    out_dir = Path(args.out_dir)
    today = datetime.date.today().isoformat()
    output.write_csv(rows, out_dir / f"{today}.csv")
    output.write_markdown(rows, out_dir / f"{today}.md", heading=args.heading)
    companies = len({r["company"] for r in rows})
    print(f"{args.heading} · {len(rows)} jobs · {companies} companies · "
          f"{total - len(rows)} duplicates merged")
    print(output.table(rows))
    print(f"Saved → {out_dir / (today + '.md')} and .csv")
    return 0


def cmd_discover(args) -> int:
    try:
        urls = [u.strip() for u in Path(args.urls).read_text(encoding="utf-8").splitlines() if u.strip()]
    except FileNotFoundError:
        _err(f"urls file not found: {args.urls}")
        return 2
    try:
        report = discover_mod.discover(urls)
    except CompanyFileError as e:
        _err(str(e))
        return 2
    if not args.save:
        print(json.dumps(report, indent=1, ensure_ascii=False))
        return 0
    added = add_user_companies(report["new"])
    print(f"Added {added} companies to {user_file()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="jobs.py", description="Israel job search")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("boards", help="search employer job boards")
    b.add_argument("--titles", default="jobs/titles.txt")
    b.add_argument("--out", default="jobs/boards.csv")
    b.set_defaults(func=cmd_boards)
    t = sub.add_parser("techmap", help="search techmap (LinkedIn jobs)")
    t.add_argument("--titles", default="jobs/titles.txt")
    t.add_argument("--out", default="jobs/techmap.csv")
    t.set_defaults(func=cmd_techmap)
    m = sub.add_parser("merge", help="merge result CSVs into one list")
    m.add_argument("--inputs", nargs="+", default=["jobs/boards.csv", "jobs/techmap.csv"])
    m.add_argument("--out-dir", default="jobs")
    m.add_argument("--heading", default="Jobs")
    m.set_defaults(func=cmd_merge)
    d = sub.add_parser("discover", help="find new company boards in a list of URLs")
    d.add_argument("--urls", required=True, help="text file, one URL per line")
    d.add_argument("--save", action="store_true", help="add the new boards to your personal list")
    d.set_defaults(func=cmd_discover)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
