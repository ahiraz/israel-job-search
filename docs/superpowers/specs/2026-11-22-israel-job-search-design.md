# israel-job-search — design

## Intent
Open-source the job-search ability built privately in hermis-v2 so any job seeker
can run it from their own Claude Code. They type a job title, get a merged list of
matching open jobs in Israel, and read it. Nothing more.

## Users and success
- Individual job seekers in their own Claude Code. They read the list; no
  applying, tracking or CV scoring.
- Success: install from GitHub in two commands, run `find-jobs`, get a deduped list
  from company ATS boards + techmap in a couple of minutes, with no keys or logins
  required for the search itself.

## Goals
1. Suggest title permutations from a user's title; user confirms.
2. Search ~283 Israeli employers' public ATS boards for those titles (Israel only).
3. Search techmap (github.com/mluggy/techmap) CSVs for those titles (covers LinkedIn jobs).
4. Merge, dedupe, show, and save the combined list.
5. Separate capability: discover new companies' boards and add them to `companies.json`.

## Non-goals
- CV matching, scoring, applying, application tracking.
- Telegram/Hermes delivery, cron, servers, databases.
- Sources that need a login (Secrethunter, Scalefox, LinkedIn directly).
- Markets outside Israel.

## Anti-goals
- Inventing jobs: every row comes from a script's fetched data, never from the model.
- Scraping sources whose terms forbid it (Getro/Consider VC job boards — same rule as jobsworm).
- Silent edits to `companies.json`: discovery always asks before writing.

## Approaches considered
- **A. One Claude Code plugin with 5 skills (chosen).** One install, each step usable alone,
  ships a shared `companies.json` updated through plugin updates.
- B. Python CLI package + thin skill: reusable outside Claude but two install steps,
  Claude adds little.
- C. Loose skills folder copied by hand: simplest to publish, no clean updates.

## Install (decided)
Public GitHub repo containing `.claude-plugin/marketplace.json` and `.claude-plugin/plugin.json`:
```
/plugin marketplace add <owner>/israel-job-search
/plugin install israel-job-search@israel-job-search
```
Updates via `/plugin marketplace update`. Requirement: Python 3.10+, stdlib only
everywhere, including discovery (port jobsworm's httpx/asyncio code to urllib + threads)
— no pip install step.

## Skills and outputs (decided)
Output goes to the terminal and to `./jobs/` in the user's current directory.

1. **job-titles** — model suggests 4–8 variants of the user's title; user ticks
   which to keep; excludes default to Team Lead / Tech Lead only when the user's title
   is managerial (builder's call to make this rule clean). Saves `./jobs/titles.txt`.
   This is the only step where the model generates content, and it generates search
   terms, not results.
2. **search-boards** — runs the ported ATS fetch against `companies.json` with the
   titles; Israel-only. Prints a table (Company, Title, City, Posted, Link) plus how many
   boards were searched/failed. Saves `./jobs/boards.csv`.
3. **search-techmap** — downloads all 19 techmap category CSVs (small) and filters by
   title only; no level filter, the titles carry the seniority. Same table, labelled "LinkedIn via techmap". Saves `./jobs/techmap.csv`.
4. **update-companies** — run only on request, never inside find-jobs. Searches the ATS
   domains (`site:job-boards.greenhouse.io "Tel Aviv"`, Ashby, Lever, Comeet hosted…),
   using Claude Code's built-in WebSearch (decided: no API key). The model runs ~10–20
   searches and hands the result URLs to a script that extracts board tokens, drops known
   ones, verifies each has ≥1 Israeli job, shows the new ones and asks before saving.
   Additions go to the user's own file `~/.config/israel-job-search/companies.json`,
   merged with the shipped list at search time, so plugin updates never wipe them.
   Additions are the user's responsibility; the skill does not suggest upstream PRs and
   the repo owner does not commit to maintaining contributions. Cost ~20–40k tokens/run.
5. **find-jobs** — 1 → 2 → 3, then merge and dedupe; newest first; a "Found in" column
   (boards / techmap / both). Saves `./jobs/<date>.md` and `.csv`.

## Matching (decided as defaults)
- Reuse hermis `role_filter.py` semantics: case-insensitive whole-word, `*` = up to 3 words,
  include/exclude lists — but the include list comes from `titles.txt` instead of the
  hard-coded management `roles.txt`.
- One shared title rule for both sources, including the Team Lead / Tech Lead exclusion.
- Israel filter: reuse `adapters.in_israel`.

## Constraints
- No Hermes/Telegram/`/home/ubuntu` paths; all paths relative to the plugin root
  (`${CLAUDE_PLUGIN_ROOT}`) or the user's cwd.
- Polite crawling: keep hermis's 5-worker ceiling and per-host throttle; honest bot User-Agent
  pointing at the repo.
- `companies.json` tokens are public identifiers (add a gitleaks allowlist like jobsworm).
- License: MIT (builder's call unless the owner objects).

## Source code to port
- `hermis-v2/skills/hermis-jobs-ats/{adapters.py, fetch_ats.py, role_filter.py, companies.json}` + tests.
- `hermis-v2/skills/hermis-jobs-techmap/fetch_techmap.py` (generalise beyond Manager level and `software.csv`).
- `jobsworm/scripts/seed/{detect_ats.py, verify_ats.py, add_detected.py}` for discovery/verification.

## README (decided)
The repo README explains what each of the 5 skills does (with sample output), how to
install from GitHub, requirements (Python 3.10+), and that `update-companies` uses
WebSearch and saves to the user's own config file.

## Left to the builder
File layout inside the plugin, CSV/MD formatting details, dedupe key (URL normalisation,
then company+title), test strategy, README wording.
