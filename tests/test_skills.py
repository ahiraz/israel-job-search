import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ("job-titles", "search-boards", "search-techmap", "find-jobs", "update-companies")
SCRIPT = '"${CLAUDE_PLUGIN_ROOT}/scripts/jobs.py"'


def read(name):
    text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert m, f"{name}: missing frontmatter"
    meta = dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)
    return {k.strip(): v.strip() for k, v in meta.items()}, m.group(2)


@pytest.mark.parametrize("name", SKILLS)
def test_frontmatter(name):
    meta, _ = read(name)
    assert meta["name"] == name
    assert len(meta["description"]) > 40


@pytest.mark.parametrize("name", SKILLS)
def test_never_invent(name):
    _, body = read(name)
    assert "Never invent job listings" in body


@pytest.mark.parametrize("name", [s for s in SKILLS if s != "job-titles"])
def test_runs_the_cli(name):
    _, body = read(name)
    assert SCRIPT in body


def test_find_jobs_never_discovers():
    _, body = read("find-jobs")
    assert " discover" not in body.replace("update-companies", "")


def test_job_titles_has_no_default_exclusions():
    _, body = read("job-titles")
    assert "no default exclusions" in body.lower()


def test_find_jobs_clears_previous_results_first():
    _, body = read("find-jobs")
    assert "rm -f ./jobs/boards.csv ./jobs/techmap.csv" in body
    assert body.index("rm -f") < body.index(" boards --titles")


def test_update_companies_saves_the_approved_report():
    _, body = read("update-companies")
    assert "--report ./jobs/discover_report.json" in body
    assert "discover --save ./jobs/discover_report.json" in body
