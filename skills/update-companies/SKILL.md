---
name: update-companies
description: Discover Israeli employers whose job boards (Greenhouse, Ashby, Lever, Comeet, SmartRecruiters, Recruitee) are not yet in the search list, verify they have jobs in Israel, and add them to the user's personal company list. Use only when the user asks to update, refresh or expand the company list, or asks why a company is missing.
---

You are finding employer job boards that the search does not cover yet. **Never invent job listings or companies**: a board is added only if the script verified it.

## Steps

1. **Search the web.** Use your WebSearch tool to run these queries, one at a time (about 10–20 searches in total). Collect every result URL.

   - `site:job-boards.greenhouse.io "Tel Aviv"`
   - `site:job-boards.greenhouse.io Israel`
   - `site:boards.greenhouse.io Israel`
   - `site:jobs.ashbyhq.com "Tel Aviv"`
   - `site:jobs.ashbyhq.com Israel`
   - `site:jobs.lever.co "Tel Aviv"`
   - `site:jobs.lever.co Israel`
   - `site:comeet.com/jobs Israel`
   - `site:comeet.com/jobs "Tel Aviv"`
   - `site:jobs.smartrecruiters.com Israel`
   - `site:recruitee.com Israel`
   - then repeat the Greenhouse and Comeet queries with `Herzliya`, `Haifa`, `Jerusalem`, `Petah Tikva`, `Ramat Gan` while they keep returning new boards.

   If the user named a specific company that is missing, also search `"<company>" careers` and `"<company>" greenhouse OR comeet OR lever OR ashby`.

2. **Write the URLs** to a temporary file, one per line, for example `./jobs/discover_urls.txt`.

3. **Check them** (no changes yet):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobs.py" discover --urls ./jobs/discover_urls.txt
```

   It prints JSON: `new` (boards not in any list, verified to have at least one job in Israel, with `jobs_israel` counts) and `skipped` (with reason `known`, `no israeli jobs`, `fetch failed`, or `no comeet token on page`).

4. **Show the user** a short summary: how many boards were found, how many are new, then a table of the new ones (name, provider, Israeli jobs). Ask: "Add these N companies to your personal list?"

5. **Only if the user says yes**, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobs.py" discover --urls ./jobs/discover_urls.txt --save
```

   Report the `Added N companies to <path>` line. Explain that the personal list lives in that file, is used by every future search alongside the built-in list, survives plugin updates, and is the user's own to maintain.

Never edit the plugin's own `data/companies.json`.
