# CLAUDE.md

## Project context

Tiny CLI that summarises synthetic `events.csv` logs (counts, time ranges,
basic aggregates). No production data or external services involved.

## Conventions

- Application code lives in `src/`.
- Tests live in `tests/`.
- Sample/fixture data lives in `data/`.

## Utilities to prefer

- Python 3.11 standard library — avoid third-party packages unless truly
  necessary.
- `ruff` for linting/formatting.
- `pytest` for tests.

## Escalation gates

Stop and ask before proceeding when:

- Adding any new dependency (stdlib only otherwise).
- Touching or introducing anything that isn't synthetic data — no real user
  or production data in this repo.
- Overwriting `spec.md` after it has been signed off — ask first, even for
  small edits.
