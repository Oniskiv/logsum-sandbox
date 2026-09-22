# by-hand-vs-agent.md

Comparing the by-hand build on `main` (three human-reviewed PRs, with
decisions recorded in `ci-notes.md`, `refactor-notes.md`, `questions.md`)
against the isolated agent replay on this branch (one autonomous subagent
pass, walled off from all of the above, documented in
`provenance-replay.md`). Grounded in the real deltas that comparison
surfaced, not "looked the same" — three of those deltas are load-bearing
enough to change how much I'd trust either output unreviewed.

## 1. What both produced

Functionally overlapping CLIs: identical grouping/normalisation, identical
output on every shared fixture and on `data/sample_events.csv` (byte-for-byte
identical `summary.csv`), identical `argparse.error()`-override trick to
force exit `1` on bad arguments. Different internal shape and different
answers at the edges spec.md doesn't cover — see §3.

By-hand (`main`): built across three merged PRs (`ci-workflow`,
`refactor-clarity`, `min-count-flag`), a documented CI failure and fix
(`ci-notes.md` — `F821` on a missing `datetime` import, caught by a real CI
run, not locally first), a deliberate refactor with a human "keep/remove"
decision on each change (`refactor-notes.md`), and a later audit pass
(`questions.md`) re-verifying its own citations against the code line by
line.

Agent replay: one `general-purpose` subagent, ~5 minutes, given only
`spec.md`, the relevant `CLAUDE.md` conventions, and the fixture CSVs —
produced `src/logsum.py`, `tests/test_logsum.py` (19 tests), `.github/
workflows/ci.yml`, and one self-chosen refactor, green on first report.

## 2. Where the agent saved time

- No red CI run in the loop. `ci-notes.md` shows the missing `datetime`
  import only being caught after a push, on a real GitHub Actions run. The
  agent ran `ruff check .` / `pytest -v` itself before calling anything
  done, so that class of mistake never had the chance to reach a "PR" at
  all — the entire diagnose/fix/re-push cycle main needed for that bug
  didn't exist here.
- One pass instead of three merges. The by-hand build split naturally into
  CI setup, then a refactor, then a feature flag, each its own PR and review
  cycle. The agent produced the equivalent of all three (structure, clarity
  pass, and matching `--min-count` support) in a single unsupervised run.
- No separate archaeology step. `questions.md` exists because someone later
  needed to ask "where is the grouping rule" and "how is missing level
  handled" and had to re-derive the answers from the code days after the
  fact, then re-verify every citation. The agent's design reasoning came
  back in its own final report, at the moment the code was written, for
  free.

## 3. Where it went wrong or shorter

- **Header-validation gap — confirmed live, not theoretical.** Fed both
  implementations a CSV with header `timestamp,service,message` (no `level`
  column at all, not just a blank value). `main`: exit `1`, `"missing
  required column(s): level"`. Agent: exit `0`, treats the absent column
  exactly like a blank one, writes `auth,UNKNOWN,1,...` as if nothing were
  wrong. `spec.md` §4 only ever discusses a blank/missing *value*, never a
  structurally absent *column*, so neither reading violates the written
  spec — but this is the wrong direction to be silent in for a tool whose
  entire purpose is a trustworthy at-a-glance summary. A CSV pointed at the
  wrong file, or missing a column because of an upstream schema change,
  should fail loudly, not get quietly summarized as normal traffic.
- **The stderr contract got weaker, not just reworded.** `main` writes to
  stderr only when `skipped_rows > 0`. The agent writes it unconditionally,
  including `skipped_rows: 0` on every clean run. That's a real behavior
  change to default-case output — anything downstream that greps stderr on
  the assumption "nothing printed means nothing was skipped" silently breaks
  against the agent's version. Nothing in `spec.md` pins this down either
  way, and nothing caught it before it shipped, because there was no review
  step between "agent finished" and "files are now in place" — the decision
  the agent made alone, on the fly, is exactly the kind of thing five
  minutes of human read-through would have flagged.
- **Coverage lost, not just moved.** `main`'s parametrized unwritable-output
  test covers both a missing parent directory *and* `-o` pointing at a
  directory itself. The agent's suite only covers the missing-parent case.
  Same code path underneath (a caught `OSError`), but one fewer verified
  edge case than what it replaced.

## 4. What the agent did better

- Its first-pass data model — a `GroupKey` `NamedTuple` plus a `GroupStats`
  object with an `add()` method — is the *shape* `main` only reached via an
  explicit refactor (`refactor-notes.md`'s dict → `_GroupStats` dataclass
  change). The agent never had the "duplicated min/max branch logic across
  new-key/existing-key paths" problem to begin with, because it modeled the
  accumulator correctly from the first draft. Spec's requirements seem to
  point at that shape fairly directly; the agent got there without the
  detour.
- Its test for the "group with only malformed rows" case makes a real
  assertion (`("payments", "ERROR") not in data_rows`) instead of hedging.
  `main`'s equivalent test explicitly accepts either "omitted" or
  "count=0" as valid, even though `main`'s own implementation is
  deterministic and always omits. The agent's test is more honest about
  what its own code actually guarantees.
- It found a genuinely different, valid refactor target
  (`filter_groups()` pulled out of the CSV-writing loop) entirely on its
  own, with no seeded target and no visibility into what `main` had done —
  useful evidence that "find one clarity improvement" works as an
  instruction even without a known answer to aim for.

## 5. What I learned about supervised vs async

The header-validation gap is the clearest signal here. Nothing in `main`'s
own history claims `REQUIRED_COLUMNS` came from `spec.md` — it reads like
the kind of defensive addition that shows up when a human (or an agent under
live back-and-forth) asks "what if this column just isn't there" mid-review,
not something a single unsupervised read of the spec text is likely to
invent unprompted. A one-shot async agent is faithful to what's written; it
has no mechanism for surfacing what's *not* written but obviously matters,
because there's no one to free-associate the edge case out loud while it
works. That's specifically what supervision buys, and specifically what this
replay was missing.

Isolation itself leaks in exactly the way supervision would catch and
autonomy doesn't. The subagent's own environment handed it an automatic
git-status snapshot naming deleted reference files — a leak of metadata, not
content, but a leak — and the only thing standing between that and real
contamination was the subagent choosing, unsupervised, to self-report it
instead of pulling on the thread. A supervised session has a human notice
that the moment it appears on screen. An async one only surfaces it in the
final report, after the fact, for someone else to judge in hindsight —
which is what happened here.

`tests/test-notes.md`'s own isolation-breach note (an earlier session
grepping for `logsum.py`'s identifier names "just to check for
collisions," and later flagging that as a breach anyway) makes the same
point from the other direction: even deliberately blind work drifts toward
the answer key under ordinary task pressure, supervised sessions included.
The discipline has to be structural — files physically absent — more than
it can be a promise kept under instruction alone.

## 6. What I'd do differently

- Not treat "both are green" as sufficient before superseding `main` in
  place. Add a behavior-parity check — run both implementations against a
  small adversarial fixture set (missing columns, not just blank fields;
  edge cases beyond what `data/fixtures/` happens to already cover) and
  require an explicit human call on any exit-code or stderr divergence
  *before* the replay's files replace the originals. The header-validation
  gap should have blocked the rewrite, not just gotten written up
  afterward.
- Run two independently isolated replays instead of one, and diff them
  against each other before diffing either against `main`. A single agent's
  idiosyncratic choice (always printing `skipped_rows: 0`) is
  indistinguishable from "spec genuinely allows either reading" with only
  one data point — a second independent replay would tell you whether that
  choice is common or arbitrary.
- Escalate the header-validation gap as an actual spec question now, per
  `CLAUDE.md`'s own gate on editing a signed-off `spec.md` — ask whoever
  signed it off whether a structurally missing required column should be a
  documented fatal case, rather than leaving two silently incompatible
  behaviors on the same branch and hoping no one hits the gap in
  production.
