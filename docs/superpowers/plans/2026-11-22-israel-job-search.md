# israel-job-search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Claude Code plugin, installable from GitHub, with 5 general-purpose skills that turn a user's job titles into one merged list of open Israeli jobs from employer ATS boards and techmap, plus an on-demand company-discovery skill.

**Architecture:** One stdlib-only Python package `jobsearch/` with a single CLI (`scripts/jobs.py`) exposing subcommands `boards`, `techmap`, `merge`, `discover`. Each skill's `SKILL.md` tells Claude which subcommand to run and how to present its output; the model only generates title suggestions and runs WebSearch for discovery, never job rows.

**Tech Stack:** Python 3.10+ stdlib (urllib, csv, json, concurrent.futures, re), pytest for tests only, Claude Code plugin format (`.claude-plugin/`, `skills/*/SKILL.md`).

**Spec:** `docs/superpowers/specs/2026-11-22-israel-job-search-design.md`

## Global Constraints

- Python 3.10+, standard library only at runtime. No `pip install` for users. pytest is a dev-only dependency.
- General-purpose: no hard-coded role family, seniority, or exclusion. Everything comes from the user's `titles.txt`.
- Israel only (`adapters.in_israel` for boards; techmap is Israel-only by source).
- Every job row comes from fetched data. Skills must say "run the script; never invent listings".
- Output to the user's cwd: `./jobs/titles.txt`, `./jobs/boards.csv`, `./jobs/techmap.csv`, `./jobs/<YYYY-MM-DD>.md` and `.csv`.
- User company additions go to `~/.config/israel-job-search/companies.json` (override with env `JOBSEARCH_CONFIG_DIR`), merged with the shipped `data/companies.json` at load. Never write to the plugin folder.
- update-companies asks before saving, and never suggests upstream PRs.
- Crawl politely: at most 5 workers, per-host gap 0.35 s, User-Agent `IsraelJobSearch/1.0 (+https://github.com/<owner>/israel-job-search)`.
- Skill scripts are invoked as `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobs.py" <subcommand> …`.
- MIT license. `.gitleaks.toml` allowlists `data/companies.json` (public board tokens).

## Review Focus

1. A `titles.txt` with an empty `[include]` section → the CLI exits 2 with "no titles in [include]" rather than returning every job. (Task 2)
2. Hebrew titles and titles with punctuation (`R&D`, `Sr.`, `מנהל/ת`) → they match after normalisation, the same way the English ones do. (Task 2)
3. A broken or bad personal `companies.json` → a clear error naming the file, not a traceback. Duplicate boards between the shipped and personal files are fetched once. (Task 3)
4. Network down or most boards failing → `boards` exits 1 and leaves the previous `boards.csv` in place. A few dead boards are listed on stderr and the run still succeeds. (Task 4)
5. The same job from both sources (techmap URLs carry `?utm_…` query strings) → merged into one row with "Found in: boards + techmap". (Task 6)

---

## File Structure

```
.claude-plugin/plugin.json          plugin manifest
.claude-plugin/marketplace.json     single-plugin marketplace (GitHub install)
data/companies.json                 shipped list (from hermis companies.json)
jobsearch/__init__.py
jobsearch/adapters.py               per-ATS fetch + in_israel (ported from hermis)
jobsearch/titles.py                 titles.txt parse + TitleFilter
jobsearch/companies.py              load shipped+user lists, dedupe, save user additions
jobsearch/boards.py                 search all boards → rows
jobsearch/techmap.py                download all category CSVs → rows
jobsearch/merge.py                  dedupe/merge rows from sources
jobsearch/output.py                 CSV / Markdown / terminal table writers
jobsearch/discover.py               URLs → candidate boards → verified new boards
scripts/jobs.py                     CLI: boards | techmap | merge | discover
skills/<name>/SKILL.md              5 skills
tests/…                             pytest, offline (HTTP mocked)
README.md  LICENSE  .gitleaks.toml  .gitignore
```

Row shape used everywhere (`Row = dict`):
`{"company": str, "title": str, "city": str, "posted": str (ISO date or ""), "url": str, "source": "boards" | "techmap"}`.
After merge, `source` becomes `"boards" | "techmap" | "boards + techmap"`.

---

### Task 1: Plugin skeleton and adapters port

**Files:**
- Create: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `jobsearch/__init__.py`, `jobsearch/adapters.py`, `data/companies.json`, `LICENSE`, `.gitignore`, `.gitleaks.toml`, `pytest.ini`
- Test: `tests/test_adapters.py`

**Interfaces:**
- Produces: `adapters.fetch_jobs(provider: str, token: str, keep=None) -> list[dict]` (job dicts with `title, location, primary_location, url, posted_at, …`), `adapters.in_israel(job: dict) -> bool`, `adapters.is_israeli(text: str) -> bool`, `adapters.http_get_json(url: str)`, `adapters.http_get_text(url: str) -> str` (new; same throttle/UA), `adapters.PROVIDERS: tuple[str, ...]`.

- [ ] **Step 1:** Copy `hermis-v2/skills/hermis-jobs-ats/adapters.py` → `jobsearch/adapters.py` and `test_adapters.py` → `tests/test_adapters.py` (fix imports to `from jobsearch import adapters`). Copy `companies.json` → `data/companies.json`.
- [ ] **Step 2: Write the failing tests**
```python
def test_user_agent_points_at_repo():
    assert adapters.USER_AGENT.startswith("IsraelJobSearch/1.0")
def test_http_get_text_uses_throttle_and_ua(monkeypatch): ...  # mock urlopen, assert UA header sent, returns decoded str
```
- [ ] **Step 3:** Run `python3 -m pytest tests/test_adapters.py -q`. Expected: the 2 new tests FAIL and the ported ones pass.
- [ ] **Step 4:** Set `USER_AGENT` per Global Constraints. Add `http_get_text` sharing `_throttle` and retries with `http_get_json`. Add a `PROVIDERS` tuple.
- [ ] **Step 5:** Write `plugin.json` (`name: "israel-job-search"`, version `0.1.0`, description, MIT license) and `marketplace.json` (`name: "israel-job-search"`, one plugin entry with `source: "./"`). Write `pytest.ini` (`testpaths = tests`).
- [ ] **Step 6:** Run `python3 -m pytest -q`. Expected: all pass. Run `claude plugin validate .` if that command is available. Expected: no errors.
- [ ] **Step 7:** Commit `feat: plugin skeleton and ATS adapters`.

### Task 2: Title file and filter

**Files:** Create `jobsearch/titles.py`; Test `tests/test_titles.py`

**Interfaces:**
- Produces: `parse_titles(text: str) -> dict[str, list[str]]` (keys `include`, `exclude`; `#` comments; blank lines ignored), `load_titles(path: Path) -> TitleFilter`, `class TitleFilter(include: list[str], exclude: list[str])` with `.accept(title: str) -> bool`, `normalize(text: str) -> str`, `class NoTitlesError(ValueError)`.

- [ ] **Step 1: Write the failing tests** (port semantics from hermis `role_filter.py`: whole-word, case-insensitive, `*` = up to 3 words, R&D→rd)
```python
def test_include_whole_word():  f=TitleFilter(["data engineer"],[]); assert f.accept("Senior Data Engineer") and not f.accept("Big Data Engineering Intern Program")  # whole phrase only
def test_star_wildcard():       assert TitleFilter(["software * manager"],[]).accept("Software Development Manager")
def test_exclude_wins():        assert not TitleFilter(["manager"],["team lead"]).accept("Team Lead Manager")
def test_no_builtin_exclusions(): assert TitleFilter(["lead"],[]).accept("Tech Lead")
def test_hebrew_and_punct():    assert TitleFilter(["מנהל פיתוח","r&d manager"],[]).accept("מנהל/ת פיתוח") and TitleFilter(["r&d manager"],[]).accept("R&D Manager")
def test_parse_sections():      assert parse_titles("[include]\nqa\n# c\n[exclude]\nintern\n")=={"include":["qa"],"exclude":["intern"]}
def test_empty_include_raises(tmp_path): (tmp_path/"t.txt").write_text("[include]\n"); pytest.raises(NoTitlesError, load_titles, tmp_path/"t.txt")
```
- [ ] **Step 2:** Run `python3 -m pytest tests/test_titles.py -q`. Expected: FAIL (module missing).
- [ ] **Step 3:** Implement. Base it on `role_filter.normalize` and `_compile`. Extend `normalize` so `/` and other punctuation become spaces and Hebrew letters are kept. Drop `[exclude_function]` and `[broad]`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit `feat: user-defined title include/exclude filter`.

### Task 3: Company lists (shipped + personal)

**Files:** Create `jobsearch/companies.py`; Test `tests/test_companies.py`

**Interfaces:**
- Produces: `user_file() -> Path` (`$JOBSEARCH_CONFIG_DIR/companies.json`, default `~/.config/israel-job-search/companies.json`), `load_companies(shipped: Path = SHIPPED) -> list[dict]` (shipped + user, deduped by `(provider, token)` with names joined as in hermis `dedupe_companies`), `known_boards() -> set[tuple[str, str]]`, `add_user_companies(new: list[dict]) -> int` (appends to the user file, skips known boards, returns the number added), `class CompanyFileError(ValueError)`.

- [ ] **Step 1: Write the failing tests:** user entries are merged in; a duplicate `(provider, token)` across the files gives one entry; invalid JSON in the user file raises `CompanyFileError` with the path in the message; a missing user file is fine; `add_user_companies` creates the directory, skips known boards and never touches the shipped file (assert its mtime is unchanged).
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Port `dedupe_companies` from hermis `fetch_ats.py:48`. Entry shape: `{name, domain, provider, token, careers_url}`.
- [ ] **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Commit `feat: shipped + personal company lists`.

### Task 4: Board search and CLI `boards`

**Files:** Create `jobsearch/boards.py`, `jobsearch/output.py`, `scripts/jobs.py`; Test `tests/test_boards.py`, `tests/test_output.py`

**Interfaces:**
- Consumes: `adapters.fetch_jobs`, `adapters.in_israel`, `TitleFilter.accept`, `load_companies`.
- Produces: `search_boards(companies, accept, workers=5) -> tuple[list[Row], list[tuple[str, str]]]` (rows plus `(company, error)` failures), `class BrokenRun(RuntimeError)` (raised when no board succeeded, or more than half failed), `output.write_csv(rows, path)`, `output.read_csv(path) -> list[Row]`, `output.write_markdown(rows, path, heading: str)`, `output.table(rows, limit=50) -> str`. CLI: `jobs.py boards --titles PATH --out PATH`. It prints `Searched N company boards (F failed)`, then `Found K jobs in Israel`, then the table. Exit 0 = ok, 1 = BrokenRun (the old `--out` is kept), 2 = bad input (NoTitlesError / CompanyFileError).

- [ ] **Step 1: Write the failing tests** (monkeypatch `adapters.fetch_jobs`): only Israeli jobs whose titles are accepted are returned, with `source == "boards"`; one raising board → listed in failures and the run succeeds; 3 of 4 boards raising → `BrokenRun`; the CLI with empty `[include]` exits 2; on BrokenRun an existing `--out` file is left unchanged; `write_csv`→`read_csv` round-trips; `table` sorts newest `posted` first.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Port the thread-pool logic from hermis `fetch_ats.run` (drop the failure-state file). Map job→Row: `city` = `primary_location or location`, `posted` = the first 10 characters of `posted_at`. Write to `--out` only after a successful run (temp file + rename).
- [ ] **Step 4:** Run them. Expected: PASS. Then run a live smoke test: `python3 scripts/jobs.py boards --titles <tmp with "[include]\nbackend engineer"> --out /tmp/b.csv`. Expected: exit 0, more than 0 jobs.
- [ ] **Step 5:** Commit `feat: board search CLI`.

### Task 5: Techmap search and CLI `techmap`

**Files:** Create `jobsearch/techmap.py`; Test `tests/test_techmap.py`

**Interfaces:**
- Produces: `CATEGORIES: tuple[str, ...]` (the 19 file names: admin, business, data-science, design, devops, finance, frontend, hardware, hr, legal, marketing, procurement-operations, product, project-management, qa, sales, security, software, support), `parse_csv(text: str, accept) -> list[Row]`, `search_techmap(accept) -> tuple[list[Row], list[str]]` (failed categories). Source URL: `https://raw.githubusercontent.com/mluggy/techmap/main/jobs/{name}.csv`. CLI: `jobs.py techmap --titles PATH --out PATH`, with the same exit codes. It exits 1 if every category fails.
- Columns: `company,category,size,title,level,city,url,updated`. Row: `city`←city, `posted`←updated, `source="techmap"`. No level filter.

- [ ] **Step 1: Write the failing tests:** `parse_csv` with a sample that includes a UTF-8 BOM header and a Hebrew city keeps only accepted titles; the same URL in two categories → one row; all downloads failing → CLI exit 1.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Decode with `utf-8-sig` and download with up to 5 threads via `adapters.http_get_text`.
- [ ] **Step 4:** Run the tests and a live smoke test. Expected: PASS, and the live run finds more than 0 rows for "backend engineer".
- [ ] **Step 5:** Commit `feat: techmap search CLI`.

### Task 6: Merge and CLI `merge`

**Files:** Create `jobsearch/merge.py`; Test `tests/test_merge.py`

**Interfaces:**
- Produces: `normalize_url(url) -> str` (lowercase host, drop the query string and fragment, strip the trailing `/`), `merge(*row_lists) -> list[Row]` (key 1: normalised URL; key 2: `(normalize(company), normalize(title))` via `titles.normalize`; sources joined in the order `"boards + techmap"`; earliest non-empty `posted` kept; sorted newest first). CLI: `jobs.py merge --inputs A.csv B.csv --out-dir ./jobs --heading TEXT` writes `<YYYY-MM-DD>.md` and `.csv` and prints `N jobs · C companies · D duplicates merged` and the table. A missing input file prints a warning and is skipped.
- [ ] **Step 1: Write the failing tests:** a techmap URL with `?utm_source=…` merges with the same board URL → one row, `source == "boards + techmap"`; same company and title with different URLs → merged; different titles → kept apart; ordering is newest first with empty `posted` last.
- [ ] **Step 2:** Run them. Expected: FAIL. **Step 3:** Implement. **Step 4:** Run them. Expected: PASS.
- [ ] **Step 5:** Commit `feat: merge sources into one list`.

### Task 7: Discovery and CLI `discover`

**Files:** Create `jobsearch/discover.py`; Test `tests/test_discover.py`

**Interfaces:**
- Consumes: `adapters.fetch_jobs`, `adapters.in_israel`, `adapters.http_get_text`, `known_boards`, `add_user_companies`.
- Produces: `extract_boards(urls: list[str]) -> list[tuple[str, str]]` (`(provider, token)`; port the fingerprint regexes and `JUNK`/`clean` from jobsworm `detect_ats.py:60-95`, limited to the providers `adapters` supports). `resolve_comeet(slug: str, uid: str) -> str | None` fetches the hosted page `https://www.comeet.com/jobs/{slug}/{uid}` and returns `"uid::token"` using `RX_COMEET_TOK`. `verify(provider, token) -> dict | None` returns `{name, provider, token, careers_url, jobs_israel}` if at least 1 Israeli job, else None. CLI: `jobs.py discover --urls FILE [--save]`. Without `--save` it prints JSON `{"new": [...], "skipped": [{"board":…, "reason":"known|no israeli jobs|fetch failed"}]}`. With `--save` it calls `add_user_companies` and prints `Added N companies to <path>`.
- [ ] **Step 1: Write the failing tests:** `https://job-boards.greenhouse.io/daylightsecurity` → `("greenhouse","daylightsecurity")`; also `jobs.ashbyhq.com/x`, `jobs.lever.co/x/uuid`, `boards.eu.greenhouse.io/x`; junk tokens (`embed`, `jobs`) dropped; known boards are reported as `known`; a board with only US jobs is reported as `no israeli jobs`; `--save` writes into `JOBSEARCH_CONFIG_DIR`.
- [ ] **Step 2:** Run them. Expected: FAIL. **Step 3:** Implement with threads (max 5). Company name = the board's display name if the feed gives one, else the token. **Step 4:** Run them. Expected: PASS. Live check: `echo https://job-boards.greenhouse.io/daylightsecurity > /tmp/u.txt && python3 scripts/jobs.py discover --urls /tmp/u.txt` lists Daylight as new with `jobs_israel >= 1`.
- [ ] **Step 5:** Commit `feat: company discovery from ATS URLs`.

### Task 8: The five skills

**Files:** Create `skills/{job-titles,search-boards,search-techmap,find-jobs,update-companies}/SKILL.md`; Test `tests/test_skills.py`

**Interfaces:** Each SKILL.md has frontmatter `name` and `description` that says when to use it, and its body runs only the CLI commands above.

- [ ] **Step 1: Write the failing test:** for each of the 5 skills, the frontmatter parses, `name` matches the folder, the body contains `${CLAUDE_PLUGIN_ROOT}/scripts/jobs.py` (except job-titles) and the sentence "Never invent job listings".
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Write the skills:
  - **job-titles:** ask for the title if it isn't given; suggest 4–8 variants in English, plus Hebrew where common; let the user pick; ask for exclusions (no defaults); write `./jobs/titles.txt` with `[include]`/`[exclude]`; if the file already exists, show it and ask whether to reuse it or replace it.
  - **search-boards / search-techmap:** need `./jobs/titles.txt` (otherwise run job-titles first); run the CLI; show its output; on exit 1 or 2 report the stderr message and stop.
  - **find-jobs:** job-titles → `boards` → `techmap` → `merge --inputs ./jobs/boards.csv ./jobs/techmap.csv --out-dir ./jobs`. If one source failed, still merge the other and say which source failed. Never runs discovery.
  - **update-companies:** run 10–20 WebSearch queries (`site:job-boards.greenhouse.io "Tel Aviv"`, `site:job-boards.greenhouse.io Israel`, `site:jobs.ashbyhq.com Israel`, `site:jobs.lever.co Israel`, `site:comeet.com/jobs`, `site:jobs.smartrecruiters.com Israel`, plus variants for Herzliya, Haifa, Jerusalem, Petah Tikva…); write every result URL to a temp file; run `discover --urls`; show the new boards; ask; on yes, run with `--save`; say where the file is and that the additions are the user's own.
- [ ] **Step 4:** Run the test. Expected: PASS.
- [ ] **Step 5:** Commit `feat: five skills`.

### Task 9: README and end-to-end check

**Files:** Create `README.md`

- [ ] **Step 1:** Write the README: what it does; install (`/plugin marketplace add <owner>/israel-job-search`, `/plugin install israel-job-search@israel-job-search`, update with `/plugin marketplace update`); requirement (Python 3.10+); one section per skill with what it does and a sample output (from the design conversation); where files go (`./jobs/`, `~/.config/israel-job-search/companies.json`); that update-companies uses WebSearch (~20–40k tokens) and that personal additions are the user's responsibility; sources and credit (employer ATS boards, techmap by mluggy, company list derived from jobsworm); MIT.
- [ ] **Step 2:** Run the end to end from a scratch directory: install the plugin locally (`/plugin marketplace add /path/to/repo`), run find-jobs for "Backend Engineer" excluding "intern", and confirm the `./jobs/<date>.md` file exists with rows from both sources. Run `python3 -m pytest -q`. Expected: all pass.
- [ ] **Step 3:** Commit `docs: README with install and skill guide`.
