# provenance-replay.md

Provenance note for the `agent-replay` branch: an isolated replay of the
`logsum` CLI build (spec → code → tests → CI → one refactor), run to check
whether `spec.md` alone is sufficient to reproduce the behaviour already
shipped on `main`. Written by the orchestrating session after the fact,
comparing an independently-produced implementation against the known one.

## Why this needed a second pass

The first draft of the plan for this task was rejected on review: it framed
itself as testing spec-sufficiency, but the actual planning had already read
`main`'s `src/logsum.py`, its tests, and `refactor-notes.md`, and it wrote
the "one refactor" step as "re-derive the same refactor recorded in
`refactor-notes.md`." That's not independent reproduction — a close match
under those conditions would have shown nothing except that reading and
copying works. The plan was rewritten so the actual implementation work
happened inside a subagent walled off from the answer key, with the
comparison below written afterward by the (already-contaminated)
orchestrator, not the implementer.

## Isolation methodology

1. Before invoking the implementer, the following were physically relocated
   out of the working tree into an OS temp directory outside the repo (so no
   in-repo `Glob`/`Read` could reach them, and so the `Write` tool's
   "read-before-overwrite" requirement couldn't force a read of the answer):
   `src/logsum.py`, `tests/test_logsum.py`, `.github/workflows/ci.yml`,
   `ci-notes.md`, `refactor-notes.md`, `questions.md`, `tests/test-notes.md`,
   `data/summary.csv` (the exact expected output for `data/sample_events.csv`
   — answer-key material in CSV form), and `out.csv` (a partial CLI output,
   same problem in miniature). Stale `.pyc` files for the relocated modules
   were moved too.
2. A fresh `general-purpose` subagent was given the full text of `spec.md`
   and the relevant `CLAUDE.md` conventions inline, an explicit allow-list
   (`spec.md`, `CLAUDE.md`, `data/fixtures/*.csv`, `data/sample_events.csv`
   as input only), an explicit instruction not to search for or use anything
   else, and an explicit instruction not to run any `git` command (this
   repo's history contains the reference implementation; git log/show/etc.
   would have been a direct route around the file relocation).
3. After it finished, the relocated notes/output files were restored
   unchanged; the subagent's new `src/logsum.py`, `tests/test_logsum.py`,
   and `.github/workflows/ci.yml` were kept in place, superseding the
   originals (per the "rewrite in place" decision for this replay). The
   original files were kept in the temp directory, not the repo, purely for
   this comparison.

**Honest limit:** this is instruction-enforced isolation, not a technical
sandbox — nothing prevents an agent with `Read`/`Glob` from disobeying. Two
things happened worth naming plainly rather than glossing over:
- The subagent's environment included an automatic git-status snapshot (the
  same kind of context this harness gives every session at start-up) that
  listed deleted paths including a prior `src/logsum.py` and
  `tests/test_logsum.py`. This is metadata (paths only, no content) — the
  subagent reported it unprompted, did not query it further, and ran no git
  commands. Noted as a leak of *existence*, not of *content*.
- `tests/test-notes.md` (restored after, one of the relocated files) records
  that an **earlier** human/AI session doing this same kind of black-box
  test-writing task had its own isolation breach: it ran `grep` for
  `logsum.py`'s function/class names to sanity-check its test file didn't
  collide with internal identifiers, which is itself "reading the file" even
  without reading logic. That earlier session flagged it rather than
  treating "no leakage found" as "isolation maintained" — the same standard
  this replay is trying to hold itself to.

## Comparison: independent implementation vs. `main`

Ran both implementations against `data/sample_events.csv` and the shared
`data/fixtures/*.csv`. The independent implementation is otherwise unaware
these fixtures were curated for spec coverage — it treated them as arbitrary
input and derived expected output from `spec.md` directly.

### Where they converge (real signal that spec.md is doing the work)

- **Identical output rows** for `data/sample_events.csv` — same groups, same
  `count`, same verbatim `first_seen`/`last_seen`, same insertion order.
  Byte-for-byte identical CSV body.
- **Same core data model**, arrived at independently: a per-`(service,
  level)` accumulator object holding a parsed `datetime` for comparison plus
  the original raw string for verbatim output, with an `update`/`add` method
  encapsulating the min/max branching. `main` reached this shape via a
  refactor (see below); the independent implementation wrote it that way
  from the start.
- **Identical technique for exit codes**: both subclass
  `argparse.ArgumentParser` and override `error()` so *every* argument error
  exits `1` instead of argparse's default `2`, leaving `-h/--help` on
  argparse's normal exit-`0` path. Two independent authors landing on the
  same non-obvious trick is a good sign spec §7's "no separate exit code for
  argument errors" wording points there fairly directly.
- **Same resolution of the §5 ambiguity** that `tests/test-notes.md` already
  flags explicitly: whether a `(service, level)` group whose only rows are
  malformed should be omitted or appear with `count=0`. Both implementations
  omit it entirely (a group dict entry is only ever created from a row that
  parsed). The independent implementation asserts this outcome directly in
  its tests; `main`'s tests hedge and accept either reading. Same behavior,
  different confidence — worth noting as a small test-quality gap on
  `main`'s side, not the independent side.

### Where they diverge (genuine spec gaps, not implementation error)

- **Missing/blank vs. structurally-absent columns.** Spec §4 only discusses
  a "blank or missing `level` field" (a value that's empty), not a CSV whose
  header lacks a `level`/`service`/`timestamp` column entirely. `main` added
  its own stricter check — `REQUIRED_COLUMNS` validated against
  `reader.fieldnames`, fatal exit `1` if any are absent — which is **not**
  something `spec.md` asks for; it's an addition beyond the letter of the
  spec. The independent implementation has no such check: a CSV missing the
  `level` column entirely is treated the same as one with a blank `level`
  value (row counted, `level` → `UNKNOWN`, exit `0`). Verified directly:
  ```
  # input: timestamp,service,message header only (no "level" column)
  main:         exit 1, "missing required column(s): level"
  independent:  exit 0, row counted under level=UNKNOWN
  ```
  Both are consistent with a plain reading of `spec.md` §4 taken literally;
  neither is "wrong" relative to the written spec. This is the single
  clearest finding: `spec.md` is silent on structurally malformed headers,
  and that silence produces materially different CLI behavior depending on
  who fills the gap.
- **`skipped_rows` stderr format and zero-case.** `main`:
  `"logsum: skipped N row(s) with malformed timestamps"`, printed **only
  when N > 0**. Independent: `"skipped_rows: N"`, printed **unconditionally**,
  including `N=0`. Both satisfy spec §5's "tallied... reported on stderr
  when the run finishes" — the independent implementation's own report
  explicitly flagged this as an ambiguity it had to resolve and chose
  "always print" as the simpler reading. `main`'s test suite anticipated
  format variation here too (its stderr assertion is a loose regex,
  `skip\w*\D*N\b`, rather than an exact string) but didn't anticipate the
  always-vs-conditional question.
- **Test coverage breadth differs slightly**: `main` tests both an
  unwritable-parent-directory output path *and* passing a directory itself
  as `-o`; the independent suite only covers the missing-parent-directory
  case. Minor, not a behavior difference — the implementation code paths are
  the same `except OSError` catch-all either way.

### The refactor: different target, same underlying convergence

`main`'s shipped refactor (`refactor-notes.md`) replaced an inline
"new-key-vs-existing-key" branching dict accumulator with a `_GroupStats`
dataclass exposing an `update()` method — because the original first pass
had the min/max comparison logic duplicated across both branches.

The independent implementation's first pass never had that problem: it
wrote the equivalent `GroupStats` class with an `add()` method from the
start (see "Where they converge," above), so that specific clarity issue
never arose for it to refactor. Its self-chosen refactor instead targeted a
different seam: extracting the `--min-count` threshold check out of the
CSV-writing loop into a standalone `filter_groups()` function, so filtering
(a business rule) is no longer mixed into `write_summary()` (I/O
formatting). Re-verified green after applying it, no behavior change.

Read together, this suggests the *group-accumulator* design is close to
spec-determined — both authors landed there, one from the start and one via
a documented refactor — while the *specific* refactor `main` happened to
need was a function of how its first draft was written, not something
spec.md itself was steering toward. The independent implementation still
did the exercise (found a real seam, fixed it, re-verified), just not the
same seam.

## Verification

- Implementer's own run (inside isolation, before restore):
  `ruff check .` → `All checks passed!`; `pytest -v` → `19 passed in 3.91s`.
- Orchestrator's re-run on the final working tree (after restoring the
  relocated notes/output files, subagent's `src/`/`tests/`/`.github` files
  left in place): `ruff check .` → `All checks passed!`; `pytest -v` →
  `19 passed in 5.51s`.
- Manual spot-checks against `data/fixtures/*.csv` and a synthetic
  missing-column CSV (see divergence section above) confirmed the empty-input
  (exit `1`), header-only (exit `0`, header-only output), `--min-count abc`
  (exit `1`), and missing-column-header cases.

`spec.md` was not modified. No new dependency was introduced.
