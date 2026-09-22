# questions.md

Answers below are derived only from the files named per question; nothing
here is inferred beyond what those files state.

## Where is the grouping rule?

**Files read:** [spec.md](spec.md), [src/logsum.py](src/logsum.py)

**Answer:** Rows are grouped by the pair `(service, level)`, after each
value is normalised (whitespace-stripped; `level` is also uppercased and
blank levels become `"UNKNOWN"`). `message` is explicitly excluded from the
group key. The rule is specified in `spec.md` and implemented in
`summarise()` in `src/logsum.py`, which builds the group key from the two
normalisation helper functions.

**Citations:**
- Rule definition: [spec.md:3](spec.md:3), [spec.md:5-6](spec.md:5)
  ("Group rows by `(service, level)` after normalisation. `message` is
  not part of the group key").
- Normalisation rules: [spec.md:9-14](spec.md:9).
- Implementation — key construction: [src/logsum.py:56](src/logsum.py:56)
  (`key = (normalise_service(row.get("service")), normalise_level(row.get("level")))`).
- Implementation — grouping dict: [src/logsum.py:47](src/logsum.py:47),
  [src/logsum.py:57-62](src/logsum.py:57) (insert-or-update on `key`).
- Normalisation helpers: [src/logsum.py:15-16](src/logsum.py:15)
  (`normalise_service`), [src/logsum.py:19-21](src/logsum.py:19)
  (`normalise_level`).

**Not verified:** Nothing — spec and code were both read directly and are
consistent with each other. I did not re-run the code for this question.

---

## How is missing level handled?

**Files read:** [spec.md](spec.md), [src/logsum.py](src/logsum.py),
[tests/test_logsum.py](tests/test_logsum.py)

**Answer:** A blank, whitespace-only, or missing `level` value is
normalised to the literal string `"UNKNOWN"`. The row is not dropped — it
is still counted in its `(service, "UNKNOWN")` group like any other row.

**Citations:**
- Spec rule: [spec.md:44-47](spec.md:44) ("A blank or missing `level`
  field is normalised to the literal string `UNKNOWN`. The row is still
  counted — it is not dropped.").
- Implementation: [src/logsum.py:19-21](src/logsum.py:19) —
  `normalise_level` strips whitespace, uppercases, and returns `"UNKNOWN"`
  if the resulting text is empty (`text.upper() if text else "UNKNOWN"`).
- Test coverage: [tests/test_logsum.py:128](tests/test_logsum.py:128)
  `test_blank_and_whitespace_only_level_become_unknown` and
  [tests/test_logsum.py:139](tests/test_logsum.py:139)
  `test_missing_level_rows_are_counted_not_dropped` (asserts total row
  count across groups equals the input row count, i.e. nothing is
  silently dropped).

**Not verified:** I did not re-run these specific tests as part of
answering this question (they were passing as of the last full test run
in this session, per the earlier provenance note) — I'm citing the test
file's contents, not a fresh execution.

---

## How do I run tests and CI locally?

**Files read:** [.github/workflows/ci.yml](.github/workflows/ci.yml),
[ci-notes.md](ci-notes.md), [CLAUDE.md](CLAUDE.md), [README.md](README.md)

**Answer:** CI (GitHub Actions) runs on every push and pull request using
Python 3.11: it installs `ruff` and `pytest`, then runs `ruff check .` for
linting and `pytest -v` for tests. To reproduce the same checks locally,
install the two packages and run those same two commands from the repo
root:

```bash
pip install ruff pytest
ruff check .
pytest -v
```

**Citations:**
- CI trigger and Python version:
  [.github/workflows/ci.yml:3-5](.github/workflows/ci.yml:3),
  [.github/workflows/ci.yml:13-15](.github/workflows/ci.yml:13).
- Dependency install step: [.github/workflows/ci.yml:17-18](.github/workflows/ci.yml:17)
  (`pip install ruff pytest`).
- Lint step: [.github/workflows/ci.yml:20-21](.github/workflows/ci.yml:20)
  (`ruff check .`).
- Test step: [.github/workflows/ci.yml:23-24](.github/workflows/ci.yml:23)
  (`pytest -v`).
- Documented local-verification pattern (same two commands, run before
  push): [ci-notes.md:16-18](ci-notes.md:16).
- Preferred tooling confirmation: [CLAUDE.md:18-19](CLAUDE.md:18) (`ruff`
  for linting/formatting, `pytest` for tests).
- [README.md](README.md:1) contains only the repo title — no run
  instructions there.

**Not verified / discrepancy noted:**
- I did not execute `pip install ruff pytest` in this session (both were
  already present in the environment used earlier).
- [ci-notes.md:18](ci-notes.md:18) records "`pytest -v` → 22 passed" from
  2026-09-21, but the suite now has more tests than that (new
  `--min-count` tests were added after that note was written) — that
  count in `ci-notes.md` is stale and not a live indicator of current
  suite size.
- I have not triggered or inspected an actual GitHub Actions run for the
  current working-tree state; the description of CI behaviour above is
  read directly from `ci.yml`, not observed from a live run.

## Verification

Every citation above was re-checked against a fresh read of the cited file
(line-numbered) as of this pass. Verdict key: **correct** = line range
contains exactly the text/code the claim relies on; **off-by-N** = range is
shifted or padded by N lines relative to what the claim needs;
**wrong rule** = the cited location doesn't support the claim at all;
**unverifiable** = couldn't be checked (file/tool unavailable).

| # | Citation | Claim it supports | Verdict |
|---|----------|--------------------|---------|
| 1 | [spec.md:3](spec.md:3) | §1 heading, "Exact group key" | correct |
| 2 | ~~spec.md:5-7~~ → [spec.md:5-6](spec.md:5) | "(service, level)" key, message excluded | off-by-1 (fixed below) |
| 3 | [spec.md:9-14](spec.md:9) | Normalisation rules (§2) | correct |
| 4 | [src/logsum.py:56](src/logsum.py:56) | Group key built from service+level only | correct |
| 5 | [src/logsum.py:47](src/logsum.py:47) | `groups` dict declaration | correct |
| 6 | [src/logsum.py:57-62](src/logsum.py:57) | Insert-or-update on `key` | correct |
| 7 | [src/logsum.py:15-16](src/logsum.py:15) | `normalise_service` | correct |
| 8 | [src/logsum.py:19-21](src/logsum.py:19) | `normalise_level` | correct |
| 9 | [spec.md:44-47](spec.md:44) | §4 missing-level rule | correct |
| 10 | [src/logsum.py:19-21](src/logsum.py:19) | Missing-level → `"UNKNOWN"` implementation | correct |
| 11 | [tests/test_logsum.py:128](tests/test_logsum.py:128) | Blank/whitespace level → `UNKNOWN` test | correct |
| 12 | [tests/test_logsum.py:139](tests/test_logsum.py:139) | Missing-level rows still counted test | correct |
| 13 | [.github/workflows/ci.yml:3-5](.github/workflows/ci.yml:3) | CI trigger (push/PR) | correct |
| 14 | [.github/workflows/ci.yml:13-15](.github/workflows/ci.yml:13) | Python 3.11 in CI | correct |
| 15 | [.github/workflows/ci.yml:17-18](.github/workflows/ci.yml:17) | `pip install ruff pytest` | correct |
| 16 | [.github/workflows/ci.yml:20-21](.github/workflows/ci.yml:20) | Lint step: `ruff check .` | correct |
| 17 | [.github/workflows/ci.yml:23-24](.github/workflows/ci.yml:23) | Test step: `pytest -v` | correct |
| 18 | [ci-notes.md:16-18](ci-notes.md:16) | Documented local-verification commands | correct (content is stale, not the citation — see note above) |
| 19 | [CLAUDE.md:18-19](CLAUDE.md:18) | Preferred tooling: ruff + pytest | correct |
| 20 | [README.md:1](README.md:1) | README has only a title, no run instructions | correct |

**Fix applied:** citation #2 in the "Where is the grouping rule?" answer
originally read `spec.md:5-7`. The quoted text ("Group rows by
`(service, level)` after normalisation. `message` is not part of the
group key") is fully contained in lines 5-6; line 7 is the next sentence
(rationale for excluding `message`) and isn't needed to support the quoted
claim. Citation corrected to `spec.md:5-6` and the quote's stray ellipsis
(which implied a skip that wasn't actually there — the text is contiguous)
was removed. No other citation required a change.
