# israel-job-search

Search open jobs in Israel by job title, from inside Claude Code. It searches
~280 Israeli employers' own job boards and [techmap](https://github.com/mluggy/techmap)
(which includes LinkedIn postings), then merges everything into one deduplicated
list.

- Works for any role: developer, designer, accountant, product, VP.
- No accounts, no API keys, nothing to `pip install`.
- Every job comes from a live source. Claude suggests job titles but never makes up listings.

## Install

In Claude Code:

```
/plugin marketplace add ahiraz/israel-job-search
/plugin install israel-job-search@israel-job-search
```

Requirement: **Python 3.10 or newer** available as `python3`.

To get updates later, including additions to the built-in company list:

```
/plugin marketplace update israel-job-search
```

## Quick start

Ask Claude:

> find me backend engineer jobs

That runs the **find-jobs** skill: it helps you pick titles, searches both sources and
saves the merged list under `./jobs/` in your current folder.

## The skills at a glance

| Skill | What it does | Reads | Writes | When to use it |
|---|---|---|---|---|
| **job-titles** | Suggests variations of your job title, lets you pick, asks what to exclude | — | `./jobs/titles.txt` | First, to set or change what you search for |
| **find-jobs** | The full search: uses your titles, searches both sources, then merges and deduplicates the results | `titles.txt` | `./jobs/YYYY-MM-DD.md` and `.csv` | After job-titles, every time you want fresh results |
| **search-boards** | Searches ~280 Israeli employers' own job boards | `titles.txt` | `./jobs/boards.csv` | To search company career pages only |
| **search-techmap** | Searches techmap's daily lists, which include LinkedIn postings | `titles.txt` | `./jobs/techmap.csv` | To search LinkedIn jobs only (takes seconds) |
| **update-companies** | Finds new companies and adds them to the company list the job-board search uses | — | `~/.config/israel-job-search/companies.json` | On a slow cadence (for example once a month), to pick up companies that started hiring in Israel. Never part of find-jobs. |

### How to run a skill

Say what you want in plain words ("find me data analyst jobs", "change my job titles",
"search only LinkedIn", "add missing companies") and Claude picks the skill. Or call it
directly by name:

```
/israel-job-search:find-jobs
/israel-job-search:job-titles
/israel-job-search:search-boards
/israel-job-search:search-techmap
/israel-job-search:update-companies
```

## How the skills fit together

```
            ┌──────────────────────── find-jobs ────────────────────────┐
            │                                                           │
  you ──▶   │  1. job-titles  ──▶  ./jobs/titles.txt                    │
            │                         │                                 │
            │            ┌────────────┴────────────┐                    │
            │            ▼                         ▼                    │
            │  2. search-boards           3. search-techmap             │
            │     (employer boards)          (LinkedIn via techmap)     │
            │            │                         │                    │
            │     ./jobs/boards.csv        ./jobs/techmap.csv           │
            │            └────────────┬────────────┘                    │
            │                         ▼                                 │
            │                 4. merge  ──▶  ./jobs/YYYY-MM-DD.md, .csv │
            └───────────────────────────────────────────────────────────┘

  update-companies  ──▶  ~/.config/israel-job-search/companies.json
  (separate, run when you choose)          │
                                           └──▶ used by every later search-boards run
```

- **job-titles comes first.** Both searches read `./jobs/titles.txt`. If it is missing,
  search-boards and search-techmap run job-titles for you.
- **The two searches are independent.** If one fails (for example a network problem),
  find-jobs still merges what the other found and tells you which source failed.
- **update-companies is never part of find-jobs.** Run it on a slow cadence to add new
  companies; they are searched from the next run of find-jobs or search-boards on.

### Typical workflows

| You want to… | Run |
|---|---|
| Search for the first time | **job-titles**, then **find-jobs** |
| Search again later with the same titles | **find-jobs** (it asks whether to reuse `titles.txt`) |
| Search for a different role | **job-titles** (start over), then **find-jobs** |
| See only LinkedIn jobs, quickly | **job-titles** (once), then **search-techmap** |
| See only company career pages | **job-titles** (once), then **search-boards** |
| Cover companies that started hiring recently | **update-companies** every month or so, then **find-jobs** as usual |

## Example: job-titles, then find-jobs

**Step 1: define the titles.**

> **You:** set my job titles, I'm looking for data analyst roles
>
> **Claude:** Here are variations Israeli employers post:
> 1. Data Analyst
> 2. Business Analyst
> 3. Product Analyst
> 4. BI Analyst
> 5. Senior Data Analyst
> 6. Data Insights Analyst
>
> Which should I keep?
>
> **You:** 1–4
>
> **Claude:** Any words or titles to exclude?
>
> **You:** intern, student

Claude saves `./jobs/titles.txt`:

```
[include]
data analyst
business analyst
product analyst
bi analyst
[exclude]
intern
student
```

"data analyst" already matches "Senior Data Analyst", so there's no need for a
separate senior line.

**Step 2: run the search.**

> **You:** find me jobs
>
> **Claude:** You already have `./jobs/titles.txt` (data analyst, business analyst,
> product analyst, bi analyst; excluding intern, student). Reuse it, edit it, or start over?
>
> **You:** reuse

Claude then searches both sources and merges them:

```
Searched 288 company boards (6 failed)
Found 24 jobs in Israel
Read 19 techmap categories (0 failed)
Found 29 jobs in techmap (LinkedIn via techmap)

Data Analyst · 39 jobs · 35 companies · 14 duplicates merged
Company       Title                   City            Posted      Link
Bright Data   Data Analyst            Netanya         2026-11-26  https://www.comeet.com/jobs/brightdata/…
Claroty       Product Analyst         Tel Aviv        2026-11-26  https://www.comeet.com/jobs/Claroty/…
Modellama     Data Analyst            Ra'anana        2026-11-26  https://www.comeet.com/jobs/Modellama/…
365scores     Senior Data Analyst     Tel Aviv        2026-11-25  https://www.comeet.com/jobs/365scores/…
Global-e      Data Analyst            Petah Tikva     2026-11-25  https://www.comeet.com/jobs/global-e/…
…
Saved → jobs/2026-11-26.md and .csv
```

Next time, just say "find me jobs" and reuse the same titles to get fresh results.

## Skill details

### find-jobs: the whole search in one go

Runs job-titles, then search-boards, then search-techmap, then merges the two lists.
Jobs that both sources carry appear once, with "Found in: boards + techmap".
Newest jobs come first.

```
Backend Engineer · 91 jobs · 69 companies · 27 duplicates merged
Company        Title                     City       Posted      Link
Coralogix      Backend Engineer          רמת גן     2026-11-22  https://www.comeet.com/jobs/coralogix/…
CHEQ           Backend Engineer          Tel Aviv   2026-11-22  https://www.comeet.com/jobs/cheq/…
…
Saved → jobs/2026-11-22.md and .csv
```

It does not look for new companies. Use update-companies for that.

### job-titles: choose what to search for

You give one title. Claude suggests 4–8 variations that Israeli employers actually
post, in English. You keep the ones you want and name
anything to exclude, such as `intern` or `team lead`. There are no default
exclusions.

Saved to `./jobs/titles.txt`, which you can also edit by hand:

```
[include]
backend engineer
backend developer
software * engineer     # "*" = up to 3 words, e.g. "Software Backend Platform Engineer"
[exclude]
intern
```

Matching ignores case and punctuation, and works on whole words: `backend engineer`
matches "Senior Backend Engineer (Go)" but not "Backend Engineering Manager".
`R&D` equals `RD`.

### search-boards: employers' own job boards

Searches the public job boards of ~280 Israeli tech employers (Comeet, Greenhouse,
Lever, Ashby, SmartRecruiters, Recruitee) and keeps jobs located in Israel. It takes
about 1–2 minutes.

```
Searched 283 company boards (3 failed)
Found 49 jobs in Israel
Saved → jobs/boards.csv
```

A few failed boards is normal: a company closed or moved its board.

### search-techmap: LinkedIn jobs via techmap

Reads techmap's 19 category lists (software, product, data, design, HR, sales and
more), which are refreshed daily and include LinkedIn postings. It takes a few seconds.

```
Read 19 techmap categories (0 failed)
Found 69 jobs in techmap (LinkedIn via techmap)
Saved → jobs/techmap.csv
```

### update-companies: add new companies to the search

Finds new companies and adds them to the company list the job-board search uses.
Run it on a slow cadence, for example once a month, to pick up companies that
started hiring in Israel. It is never part of find-jobs. Claude uses its
built-in web search to look for job-board pages that mention Israel
(`site:job-boards.greenhouse.io "Tel Aviv"`, Ashby, Lever, Comeet…). A script then
checks every board it finds:

```
Found 41 boards, 9 new. Verified: 5 have jobs in Israel.
  Daylight Security   greenhouse   8 Israeli jobs
  …
Add these 5 companies to your personal list? [y/n]
```

Only boards with at least one job in Israel are offered, and nothing is saved
until you say yes. A run uses roughly 20–40k tokens (10–20 web searches).

Additions go to **your personal list** at
`~/.config/israel-job-search/companies.json`. Every search uses it together with the
built-in list, and plugin updates don't touch it. It is yours to keep or edit.

## Files

| Where | What |
|---|---|
| `./jobs/titles.txt` | your titles and exclusions |
| `./jobs/boards.csv`, `./jobs/techmap.csv` | each source's results |
| `./jobs/YYYY-MM-DD.md` / `.csv` | the merged list |
| `~/.config/israel-job-search/companies.json` | companies you added (override the folder with `JOBSEARCH_CONFIG_DIR`) |
| `data/companies.json` (in the plugin) | the built-in company list |

## Running without Claude

The skills call one script, which you can also run directly:

```
python3 scripts/jobs.py boards  --titles jobs/titles.txt --out jobs/boards.csv
python3 scripts/jobs.py techmap --titles jobs/titles.txt --out jobs/techmap.csv
python3 scripts/jobs.py merge   --inputs jobs/boards.csv jobs/techmap.csv --out-dir jobs --heading "Backend Engineer"
python3 scripts/jobs.py discover --urls urls.txt --report report.json
python3 scripts/jobs.py discover --save report.json      # after you approve it
```

Exit codes: `0` ok, `1` the run failed as a whole (for example no network; earlier
results are kept), `2` a problem with your titles or companies file.

## Development

```
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/python -m pytest            # offline tests, under a second
.venv/bin/python -m pytest -m live    # end-to-end against the real sources, ~4 minutes
```

The live tests define titles and run every search the way the skills do. They pick
a job that both sources list today and check that each source finds it and that the
merge marks it "boards + techmap". They also run company discovery on Daylight
Security and check that a saved company is searched.

## Credits and sources

- Board adapters and the company list come from [jobsworm](https://github.com/baldiga/jobsworm) (MIT).
- [techmap](https://github.com/mluggy/techmap) by mluggy.
- Jobs are read from the public job-board feeds each employer publishes for its own careers page.
  Board tokens in `data/companies.json` are public identifiers, not secrets.

## License

MIT
