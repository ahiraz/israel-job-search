"""Which employers to search: the list shipped with the plugin, plus the user's own.

The shipped list (``data/companies.json``) lives in the plugin folder, which a
plugin update replaces, so additions found by update-companies are written to a
personal file instead::

    ~/.config/israel-job-search/companies.json   ($JOBSEARCH_CONFIG_DIR overrides)

Both are lists of ``{name, domain, provider, token, careers_url}``. They are
merged on every load, one entry per board (provider + token).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

SHIPPED = Path(__file__).resolve().parent.parent / "data" / "companies.json"
REQUIRED = ("name", "provider", "token")


class CompanyFileError(ValueError):
    """A companies file could not be read."""


def user_file() -> Path:
    base = os.environ.get("JOBSEARCH_CONFIG_DIR")
    if base:
        return Path(base) / "companies.json"
    return Path(os.environ.get("HOME") or Path.home()) / ".config" / "israel-job-search" / "companies.json"


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CompanyFileError(f"cannot read {path}: {e}") from None
    if not isinstance(data, list):
        raise CompanyFileError(f"{path} must contain a JSON list of companies")
    for i, entry in enumerate(data):
        missing = [k for k in REQUIRED if not isinstance(entry, dict) or not entry.get(k)]
        if missing:
            raise CompanyFileError(f"{path} entry {i}: missing {', '.join(missing)}")
    return data


def dedupe(companies: list[dict]) -> list[dict]:
    """One entry per board (provider + token). Distinct names for the same board
    are joined ("Convexum / Sentrycs"); names differing only in case/punctuation
    are not. Ported from hermis fetch_ats.dedupe_companies."""
    boards: dict[tuple, dict] = {}
    for c in companies:
        key = (c["provider"], c["token"])
        if key not in boards:
            boards[key] = {**c, "_names": [c["name"]]}
            continue
        known = {re.sub(r"\W", "", n.lower()) for n in boards[key]["_names"]}
        if re.sub(r"\W", "", c["name"].lower()) not in known:
            boards[key]["_names"].append(c["name"])
    out = []
    for b in boards.values():
        b["name"] = " / ".join(b.pop("_names"))
        out.append(b)
    return out


def load_companies(shipped: Path = SHIPPED) -> list[dict]:
    return dedupe(_read(Path(shipped)) + _read(user_file()))


def known_boards(shipped: Path = SHIPPED) -> set[tuple[str, str]]:
    return {(c["provider"], c["token"]) for c in _read(Path(shipped)) + _read(user_file())}


def add_user_companies(new: list[dict], shipped: Path = SHIPPED) -> int:
    """Append boards not already known to the user's file. Returns how many were added.
    Never writes the shipped file."""
    known = known_boards(shipped)
    path = user_file()
    current = _read(path)
    added = 0
    for c in new:
        key = (c["provider"], c["token"])
        if key in known:
            continue
        known.add(key)
        current.append({k: c.get(k, "") for k in ("name", "domain", "provider", "token", "careers_url")})
        added += 1
    if added:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(current, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
    return added
