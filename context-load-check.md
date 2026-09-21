Here's a summary of CLAUDE.md, the project instructions file:

Project context — This is a tiny CLI that summarizes synthetic events.csv logs (counts, time ranges, basic aggregates). No production data or external services are involved.

Conventions — Application code goes in src/, tests go in tests/, and sample/fixture data goes in data/.

Utilities to prefer — Python 3.11 standard library only (avoid third-party packages unless truly necessary), ruff for linting/formatting, and pytest for tests.

Escalation gates — I must stop and ask before:

Adding any new dependency (stdlib only otherwise)
Touching or introducing anything that isn't synthetic data (no real user/production data in this repo)
Overwriting spec.md after it's been signed off, even for small edits