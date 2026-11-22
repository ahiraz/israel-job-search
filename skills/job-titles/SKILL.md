---
name: job-titles
description: Define the job titles to search for in Israel. Takes the user's title, suggests a few variations, lets the user pick, asks what to exclude, and saves ./jobs/titles.txt. Use when the user wants to set or change their target job titles, or before search-boards / search-techmap when ./jobs/titles.txt does not exist.
---

You are helping a job seeker decide which job titles to search for. You produce search terms only. Never invent job listings.

## Steps

1. If `./jobs/titles.txt` already exists, show its contents and ask whether to reuse it, edit it, or start over. If they reuse it, stop here.

2. If the user has not said what title they want, ask: "What job title are you looking for?"

3. Suggest 4–8 variations of that title that employers in Israel actually post. Use real synonyms and seniority variants of the same role, and include the Hebrew form when Israeli companies commonly post it in Hebrew. Example for "Backend Engineer": Backend Developer, Server Side Engineer, Senior Backend Engineer, Software Engineer Backend, מפתח Backend. Keep the user's own title first. Present them as a numbered list and ask which to keep. The user can also add their own.

4. Ask: "Any words or titles to exclude? (for example: intern, student, team lead, or leave empty)". There are no default exclusions: only what the user names goes in `[exclude]`.

5. Write `./jobs/titles.txt` (create `./jobs/` if needed) in this exact format:

```
# Job titles for israel-job-search. Edit freely.
# One title per line. Matching ignores case and punctuation and is whole-word.
# "*" stands for up to 3 words: "software * manager" matches "Software Development Manager".
[include]
backend engineer
backend developer
[exclude]
intern
```

   Write titles in lower case. Shorter phrases match more: "backend engineer" already matches "Senior Backend Engineer", so a separate "senior backend engineer" line is only needed if the user wants seniority as the only variant.

6. Show the saved file and tell the user they can now run the search (the find-jobs skill), or edit the file by hand.
