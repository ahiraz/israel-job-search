---
name: search-boards
description: Search ~280 Israeli employers' own job boards (Comeet, Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee) for the titles in ./jobs/titles.txt, Israel only, and save ./jobs/boards.csv. Use when the user asks to search company job boards / career pages directly, or as a step of find-jobs.
---

You are searching employers' public job boards. **Never invent job listings**: every job you show must come from the script's output.

## Steps

1. If `./jobs/titles.txt` does not exist, run the job-titles skill first.

2. Run (takes about 1–2 minutes):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobs.py" boards --titles ./jobs/titles.txt --out ./jobs/boards.csv
```

3. Read the exit code:
   - **0**: show the user the script's summary lines (`Searched N company boards (F failed)`, `Found K jobs in Israel`) and the table. A few failed boards are normal (a company closed or moved its board); mention the count, don't treat it as an error.
   - **1**: the search as a whole failed (usually no network). Tell the user the message from stderr. The previous `./jobs/boards.csv`, if any, is unchanged.
   - **2**: bad input (titles file or personal companies file). Show the stderr message, which names the file to fix.

4. If `python3` is missing or older than 3.10, tell the user this plugin needs Python 3.10 or newer.
