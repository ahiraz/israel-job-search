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
/plugin marketplace add OWNER/israel-job-search
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

## The skills

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
post, including Hebrew forms where common. You keep the ones you want and name
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
`R&D` equals `RD`, and Hebrew `מפתח/ת` equals `מפתח`.

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

### update-companies: find employers the search is missing

Run it only when you want to (it is never part of find-jobs). Claude uses its
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
python3 scripts/jobs.py discover --urls urls.txt [--save]
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
