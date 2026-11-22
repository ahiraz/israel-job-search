"""The user's job titles: which to search for, and which to leave out.

Read from a plain-text file (``./jobs/titles.txt`` by default)::

    [include]
    backend engineer
    software * engineer      # "*" = up to 3 words in between
    [exclude]
    intern

Matching is case-insensitive and whole-word, on a normalised title
(punctuation ignored, "R&D" == "RD", Hebrew "מנהל/ת" == "מנהל"). A title is
kept when it matches any [include] phrase and no [exclude] phrase. There are no
built-in exclusions: everything comes from the user's file.

Ported from hermis-v2 ``role_filter.py``.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

SECTIONS = ("include", "exclude")

# "*" in a phrase = up to this many words in between.
_WILDCARD = r"(?:\w+\s+){0,3}"
# Hebrew gender slash: מנהל/ת, מפתח/ת, ראש/ת, מתכנת/ית -> the base form.
_HE_GENDER = re.compile(r"(?<=[֐-׿])\s*/\s*(?:ית|ת|ה)(?![֐-׿])")


class NoTitlesError(ValueError):
    """The titles file has nothing to search for."""


def normalize(text: str) -> str:
    """Lowercase, fold R&D to rd, fold Hebrew gender slashes, drop punctuation,
    collapse whitespace. Hebrew letters survive (they are \\w)."""
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = _HE_GENDER.sub("", t)
    t = re.sub(r"r\s*&\s*d", "rd", t)
    t = re.sub(r"[^\w*\s]", " ", t)  # keep "*" so phrases can use it
    return re.sub(r"\s+", " ", t).strip()


def _compile(phrase: str) -> re.Pattern:
    parts = []
    for tok in normalize(phrase).split(" "):
        parts.append(_WILDCARD if tok == "*" else re.escape(tok) + r"\s+")
    body = "".join(parts)
    if body.endswith(r"\s+"):
        body = body[: -len(r"\s+")]
    return re.compile(r"(?<!\w)" + body + r"(?!\w)")


def parse_titles(text: str) -> dict[str, list[str]]:
    """Parse titles.txt content into {"include": [...], "exclude": [...]}."""
    out: dict[str, list[str]] = {s: [] for s in SECTIONS}
    current = None
    for n, line in enumerate(text.splitlines(), start=1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().lower()
            if current not in out:
                raise ValueError(f"titles file line {n}: unknown section [{current}] "
                                 f"(use [include] or [exclude])")
            continue
        if current is None:
            raise ValueError(f"titles file line {n}: title before any [include]/[exclude] section")
        out[current].append(line)
    return out


class TitleFilter:
    def __init__(self, include: list[str], exclude: list[str]):
        self.include = list(include)
        self.exclude = list(exclude)
        self._inc = [_compile(p) for p in include if normalize(p)]
        self._exc = [_compile(p) for p in exclude if normalize(p)]

    def accept(self, title: str) -> bool:
        t = normalize(title)
        if any(rx.search(t) for rx in self._exc):
            return False
        return any(rx.search(t) for rx in self._inc)


def load_titles(path: Path) -> TitleFilter:
    """Read a titles file. Raises NoTitlesError if [include] is empty, FileNotFoundError
    if it does not exist, ValueError if it is malformed."""
    sections = parse_titles(Path(path).read_text(encoding="utf-8"))
    if not sections["include"]:
        raise NoTitlesError(f"no titles in [include] in {path}")
    return TitleFilter(sections["include"], sections["exclude"])
