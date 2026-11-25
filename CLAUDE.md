# Maintainer notes

## Releasing a change

Bump `version` in `.claude-plugin/plugin.json` in every push that changes the plugin
(for example 0.1.1 → 0.1.2). Claude Code caches installed plugins by version: if the
number stays the same, `/plugin marketplace update` fetches the new code but users
keep running the old copy.

## Tests

`.venv/bin/pytest` runs the offline suite; `.venv/bin/pytest -m live` hits the real sources.
