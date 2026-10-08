<!--
Title: sentence case, saying what changed ("Seeds: yellow onions in bags").
The process behind every section below is in RELEASING.md at the root of pjvjay/pantry-platform.
-->

## What and why

<!-- What changes for whoever uses this, and why. Link the issue or plan section. -->

## Release label

Add exactly one label; the release-label check reads it (RELEASING.md, "Labels"):

- [ ] `release:major`: breaks something already in use. For pantry-db: a destructive migration (dropping or renaming a table or column, narrowing a type, adding NOT NULL without a default); removing or renaming seed products or recipes that the api, the demo or the evals refer to; changing the runner's environment contract (`DB_*`, `MIGRATIONS_DIR`, `SEED_FILE`). Below 1.0.0 it bumps the minor, and the notes open with "Breaking".
- [ ] `release:minor`: new behaviour that nothing already using it notices (a migration that only adds, new seed products or recipes).
- [ ] `release:patch`: a fix or internal change to something that ships (seed corrections, the runner, the Dockerfile).
- [ ] `release:none`: changes nothing that ships (README, CI).

A PR that lands stacked PRs on main names them here, so its label is at least theirs:

Lands: <!-- e.g. #12, #13; leave empty when this PR carries no other PR -->

## Schema and seeds

- [ ] A schema change is a new numbered file in `migrations/`; no applied migration was edited.
- [ ] `seeds/seed.sql` was regenerated with `python3 scripts/gen-seed-sql.py` after any JSON seed change.
- [ ] pantry-api's copy of `seeds/products.json` and `seeds/recipes.json` is updated in a matching PR (the platform train checks they are identical).
- [ ] A new table or column has its mirror in pantry-api's `db.py`, or the PR says why not.

## Data sources

- [ ] No new data source, or each new one is listed here with its licence, size and who approved the download.
- [ ] Every price, store, origin, freshness time and nutrition value seeded comes from a cited source, or is labelled synthetic.
- [ ] No key, token or personal data is committed.

## Live smoke

Run against `demo-hub/scripts/up.sh` in DEMO_MODE in a real browser; record pass or fail per step and attach a screenshot of the final state. Write "Not applicable: <reason>" when nothing a person sees changed.

1.
2.
3.

Result:

## Tests

<!-- The commands run and their results, e.g. migrations and seeds applied twice to a fresh Postgres; gen-seed-sql.py with no diff. -->
