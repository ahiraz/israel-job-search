"""Live end-to-end tests: real network, real boards, real techmap.

    .venv/bin/python -m pytest -m live -v      (about 3–4 minutes)

They drive scripts/jobs.py exactly as the skills do, in a scratch directory with
a scratch personal company list. Job data changes daily, so the tests pick their
"specific job" from what is live at the time instead of hard-coding one.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from jobsearch import output
from jobsearch.companies import load_companies
from jobsearch.merge import normalize_url

pytestmark = pytest.mark.live

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "jobs.py"


def run(args, cwd, cfg):
    env = {**os.environ, "JOBSEARCH_CONFIG_DIR": str(cfg)}
    p = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, env=env,
                       capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout, p.stderr


@pytest.fixture(scope="module")
def search(tmp_path_factory):
    """One full find-jobs run for "backend engineer" (excluding intern)."""
    work = tmp_path_factory.mktemp("work")
    cfg = tmp_path_factory.mktemp("cfg")
    jobs = work / "jobs"
    jobs.mkdir()
    (jobs / "titles.txt").write_text("[include]\nbackend engineer\nbackend developer\n[exclude]\nintern\n",
                                     encoding="utf-8")
    results = {}
    for cmd in ("boards", "techmap"):
        results[cmd] = run([cmd], work, cfg)
    results["merge"] = run(["merge", "--heading", "Backend Engineer"], work, cfg)
    return work, cfg, results


def test_end_to_end_all_steps_succeed(search):
    work, _, results = search
    for cmd, (rc, out, err) in results.items():
        assert rc == 0, f"{cmd} failed: {err}"
    assert "Searched" in results["boards"][1] and "Found" in results["boards"][1]
    assert "LinkedIn via techmap" in results["techmap"][1]


def test_end_to_end_merged_list_has_both_sources(search):
    work, _, _ = search
    merged_files = sorted((work / "jobs").glob("20*.csv"))
    assert merged_files, "merge wrote no dated CSV"
    rows = output.read_csv(merged_files[-1])
    sources = {r["source"] for r in rows}
    assert "boards" in " ".join(sources) and "techmap" in " ".join(sources)
    assert all("backend" in r["title"].lower() for r in rows), "a row slipped past the title filter"
    assert not any("intern" in r["title"].lower() for r in rows), "an excluded title slipped through"
    md = sorted((work / "jobs").glob("20*.md"))[-1].read_text(encoding="utf-8")
    assert md.startswith("# Backend Engineer")


def test_specific_job_found_by_both_sources(search, tmp_path):
    """Pick one live job that both sources carry, search for exactly its title,
    and check that both sources find that same job and merge marks it as such."""
    work, cfg, _ = search
    boards = output.read_csv(work / "jobs" / "boards.csv")
    techmap = output.read_csv(work / "jobs" / "techmap.csv")
    board_urls = {normalize_url(r["url"]): r for r in boards}
    shared = [r for r in techmap if normalize_url(r["url"]) in board_urls]
    if not shared:
        pytest.skip("no job is listed by both sources today")
    target = board_urls[normalize_url(shared[0]["url"])]

    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / "titles.txt").write_text(f"[include]\n{target['title']}\n", encoding="utf-8")
    for cmd in ("boards", "techmap"):
        rc, _, err = run([cmd], tmp_path, cfg)
        assert rc == 0, err
    rc, _, err = run(["merge", "--heading", target["title"]], tmp_path, cfg)
    assert rc == 0, err

    def has(path):
        return any(normalize_url(r["url"]) == normalize_url(target["url"]) for r in output.read_csv(path))
    assert has(jobs / "boards.csv"), f"boards did not find {target['company']} – {target['title']}"
    assert has(jobs / "techmap.csv"), f"techmap did not find {target['company']} – {target['title']}"
    merged = output.read_csv(sorted(jobs.glob("20*.csv"))[-1])
    hit = [r for r in merged if normalize_url(r["url"]) == normalize_url(target["url"])]
    assert len(hit) == 1 and hit[0]["source"] == "boards + techmap"


def test_update_companies_finds_and_saves_daylight(tmp_path):
    """update-companies flow on search-result-like URLs: one known board, two new
    ones (Daylight on Greenhouse, Cycode on Comeet), one non-board page."""
    cfg = tmp_path / "cfg"
    known = next(c for c in load_companies() if c["provider"] == "greenhouse")
    urls = tmp_path / "urls.txt"
    urls.write_text("\n".join([
        f"https://job-boards.greenhouse.io/{known['token']}",
        "https://job-boards.greenhouse.io/daylightsecurity/jobs/5000000000",
        "https://www.comeet.com/jobs/cycode/A8.00D/backend-engineer/FF.049",
        "https://www.linkedin.com/jobs/view/123",
    ]), encoding="utf-8")

    report_file = tmp_path / "report.json"
    rc, out, err = run(["discover", "--urls", str(urls), "--report", str(report_file)], tmp_path, cfg)
    assert rc == 0, err
    report = json.loads(out)
    new = {n["token"].split("::")[0]: n for n in report["new"]}
    assert "daylightsecurity" in new and new["daylightsecurity"]["jobs_israel"] >= 1
    assert "A8.00D" in new
    assert {"board": f"greenhouse/{known['token'].lower()}", "reason": "known"} in report["skipped"]
    assert not (cfg / "companies.json").exists(), "discover without --save must not write"

    rc, out, err = run(["discover", "--save", str(report_file)], tmp_path, cfg)
    assert rc == 0 and "Added 2 companies" in out, out + err

    rc, out, _ = run(["discover", "--urls", str(urls)], tmp_path, cfg)
    assert json.loads(out)["new"] == [], "saved boards must be known on the next run"

    os.environ["JOBSEARCH_CONFIG_DIR"] = str(cfg)
    try:
        assert any(c["token"] == "daylightsecurity" for c in load_companies())
    finally:
        del os.environ["JOBSEARCH_CONFIG_DIR"]


def test_saved_company_is_searched(tmp_path):
    """A company added by update-companies shows up in the next board search."""
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "companies.json").write_text(json.dumps([{
        "name": "Daylight Security", "domain": "", "provider": "greenhouse",
        "token": "daylightsecurity", "careers_url": "https://job-boards.greenhouse.io/daylightsecurity"}]),
        encoding="utf-8")
    from jobsearch import adapters
    titles = [j["title"] for j in adapters.fetch_jobs("greenhouse", "daylightsecurity") if adapters.in_israel(j)]
    if not titles:
        pytest.skip("Daylight has no Israeli jobs today")
    jobs = tmp_path / "jobs"
    jobs.mkdir()
    (jobs / "titles.txt").write_text(f"[include]\n{titles[0]}\n", encoding="utf-8")
    rc, _, err = run(["boards"], tmp_path, cfg)
    assert rc == 0, err
    assert any(r["company"] == "Daylight Security" for r in output.read_csv(jobs / "boards.csv"))
