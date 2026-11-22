---
name: search-techmap
description: Search techmap (github.com/mluggy/techmap), a daily list of open Israeli tech jobs that includes LinkedIn postings, for the titles in ./jobs/titles.txt, and save ./jobs/techmap.csv. Use when the user asks for LinkedIn jobs or techmap, or as a step of find-jobs.
---

You are searching techmap's public job lists. **Never invent job listings**: every job you show must come from the script's output.

## Steps

1. If `./jobs/titles.txt` does not exist, run the job-titles skill first.

2. Run (takes a few seconds):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobs.py" techmap --titles ./jobs/titles.txt --out ./jobs/techmap.csv
```

3. Read the exit code:
   - **0**: show the summary lines and the table, labelled "LinkedIn via techmap". A few failed categories are listed on stderr; mention them.
   - **1**: no techmap file could be downloaded (usually no network). Report the stderr message.
   - **2**: bad titles file. Show the stderr message.
