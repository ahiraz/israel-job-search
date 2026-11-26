# israel-job-search

A Claude Code plugin that finds open jobs in Israel by job title. It searches ~280
Israeli employers' own job boards and [techmap](https://github.com/mluggy/techmap)
(which includes LinkedIn postings), and merges the results into one deduplicated list.

Works for any role. No accounts or API keys. Every listing comes from a live source.

## Install

In Claude Code:

```
/plugin marketplace add ahiraz/israel-job-search
/plugin install israel-job-search@israel-job-search
```

Requires Python 3.10 or newer as `python3`. To update later:

```
/plugin marketplace update israel-job-search
```

## Quick start

**1. Set the role you are looking for:**

```
/job-titles data analyst
```

Claude suggests variations (Business Analyst, Product Analyst, BI Analyst…). Pick the
ones to keep and name anything to exclude, such as `intern`. They are saved to
`./jobs/titles.txt`.

**2. Run the search:**

```
/find-jobs
```

It searches both sources and saves the merged list:

```
Searched 288 company boards (6 failed)
Found 24 jobs in Israel
Read 19 techmap categories (0 failed)
Found 29 jobs in techmap (LinkedIn via techmap)

Data Analyst · 39 jobs · 35 companies · 14 duplicates merged
Company       Title                 City          Posted      Link
Bright Data   Data Analyst          Netanya       2026-11-26  https://www.comeet.com/jobs/brightdata/…
Claroty       Product Analyst       Tel Aviv      2026-11-26  https://www.comeet.com/jobs/Claroty/…
365scores     Senior Data Analyst   Tel Aviv      2026-11-25  https://www.comeet.com/jobs/365scores/…
…
Saved → jobs/2026-11-26.md and .csv
```

To refresh later, run `/find-jobs` again and reuse your titles. To search for a
different role, run `/job-titles` again first.

If another plugin uses the same skill name, use the full form, for example
`/israel-job-search:find-jobs`. You can also just ask in plain words, like
"find me data analyst jobs".

## Skills

| Skill | What it does | When to run it |
|---|---|---|
| `/job-titles` | Picks the titles and exclusions to search for | First, and whenever you change role |
| `/find-jobs` | Searches both sources and merges them into one list | Every time you want fresh results |
| `/search-boards` | Searches employers' job boards only | When you want career-page jobs only |
| `/search-techmap` | Searches techmap (LinkedIn) only, in seconds | When you want LinkedIn jobs only |
| `/update-companies` | Finds new companies and adds them to the company list | Once a month or so, to cover companies that started hiring |

How they connect:

```
/job-titles        → jobs/titles.txt
/find-jobs         → /search-boards + /search-techmap → merge → jobs/YYYY-MM-DD.md, .csv
/update-companies  → your company list, used by every later job-board search
```

The two searches are independent: if one fails, find-jobs still merges what the
other found and tells you which source failed.

## Skill details

### job-titles

You give one title. Claude suggests 4–8 variations that Israeli employers actually
post, in English. You keep the ones you want and name anything to exclude. There are
no default exclusions.

The result is `./jobs/titles.txt`, which you can also edit by hand:

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

### find-jobs

Runs search-boards and search-techmap, then merges the two lists. A job that both
sources carry appears once, marked "Found in: boards + techmap". Newest jobs come
first. If `./jobs/titles.txt` does not exist yet, it runs job-titles first.

### search-boards

Searches the public job boards of ~280 Israeli tech employers (Comeet, Greenhouse,
Lever, Ashby, SmartRecruiters, Recruitee) and keeps jobs located in Israel. Takes
about 1–2 minutes. A few failed boards is normal: a company closed or moved its board.

### search-techmap

Reads techmap's 19 category lists (software, product, data, design, HR, sales and
more), which are refreshed daily and include LinkedIn postings. Takes a few seconds.

### update-companies

Finds new companies and adds them to the company list the job-board search uses.
Claude searches the web for job-board pages that mention Israel
(`site:job-boards.greenhouse.io "Tel Aviv"`, Ashby, Lever, Comeet…), and a script
checks each board it finds:

```
Found 41 boards, 9 new. Verified: 5 have jobs in Israel.
  Daylight Security   greenhouse   8 Israeli jobs
  …
Add these 5 companies to your personal list? [y/n]
```

Only boards with at least one job in Israel are offered, and nothing is saved until
you say yes. A run uses roughly 20–40k tokens (10–20 web searches).

Additions go to your personal list at `~/.config/israel-job-search/companies.json`.
Every search uses it together with the built-in list, and plugin updates don't touch it.

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
