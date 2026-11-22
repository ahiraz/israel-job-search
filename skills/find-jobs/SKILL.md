---
name: find-jobs
description: Find open jobs in Israel for a job title, end to end. Defines the titles (with suggested variations), searches employers' job boards and techmap (LinkedIn jobs), and merges everything into one deduplicated list saved under ./jobs/. Use when the user says "find me jobs", "search for <title> jobs", "job search", or similar.
---

You are running a full job search for the user. **Never invent job listings**: every job you show comes from the scripts' output.

## Steps

1. **Titles.** Run the job-titles skill (it reuses `./jobs/titles.txt` if the user wants).

2. **Employer job boards.** Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobs.py" boards --titles ./jobs/titles.txt --out ./jobs/boards.csv
```

   Tell the user it takes about 1–2 minutes. Don't show its table; just note the summary line. If it exits 1 or 2, note the stderr message and continue with techmap.

3. **Techmap (LinkedIn jobs).** Run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobs.py" techmap --titles ./jobs/titles.txt --out ./jobs/techmap.csv
```

   Note its summary line. If it exits 1 or 2, note the message.

4. **Merge.** Use the user's main title as the heading. Pass only the CSV files whose step succeeded in this run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/jobs.py" merge --inputs ./jobs/boards.csv ./jobs/techmap.csv --out-dir ./jobs --heading "<main title>"
```

5. **Show the result**: the merged summary line and table, which source failed (if any), and the path of the saved `.md` and `.csv` files. If both sources failed, say so and stop.

This skill does not look for new companies. If the user wants more employers covered, suggest the update-companies skill.
