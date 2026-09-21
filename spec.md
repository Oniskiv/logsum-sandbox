# spec.md

## 1. Exact group key

Group rows by `(service, level)` after normalisation. `message` is not part
of the group key — grouping by message as well would fragment groups, since
messages are often unique or templated with variable data.

## 2. Normalisation rules

- `service`: strip leading/trailing whitespace; case preserved as-is.
- `level`: strip whitespace, then uppercase (`info`, `Info`, `INFO` all
  collapse to the same group).
- `message`: not used for grouping and not written to `summary.csv`.

## 3. Count only, or first_seen / last_seen too

Each output row includes `count`, `first_seen`, and `last_seen` (min/max
timestamp within the group). All three are computed in a single pass.

### summary.csv header

The group key columns (`service`, `level`) are included in the output,
since otherwise a row's group would be unidentifiable. Exact header, column
order, and format:

```
service,level,count,first_seen,last_seen
```

- `service`: the normalised group key value (§2).
- `level`: the normalised group key value (§2), e.g. `UNKNOWN` for missing
  levels (§4).
- `count`: integer, number of rows in the group.
- `first_seen`, `last_seen`: the earliest/latest timestamp in the group,
  written out verbatim in the same format as the input `timestamp` column
  (no reformatting or timezone conversion — see §8).

One row per `(service, level)` group; row order is not specified (matches
the underlying dict/aggregation order, currently first-seen-group-first).
Groups with `count` below the `--min-count` threshold (§7), if given, are
omitted.

## 4. Missing level behaviour

A blank or missing `level` field is normalised to the literal string
`UNKNOWN`. The row is still counted — it is not dropped.

## 5. Malformed timestamp behaviour

A row with a timestamp that fails to parse is excluded from aggregation (it
does not affect any group's `count`, `first_seen`, or `last_seen`) but is
tallied in a `skipped_rows` counter reported on stderr when the run
finishes. A malformed timestamp never crashes the CLI.

## 6. Empty input behaviour

- Input has a header row but no data rows: write `summary.csv` with the
  header row only, exit code `0`.
- Input is completely empty (no header row at all): treated as malformed
  input — error message on stderr, exit code `1`.

## 7. CLI flags and exit codes

```
logsum --input events.csv --output summary.csv
```

- `-i / --input` (required): path to the input `events.csv`.
- `-o / --output` (default: `summary.csv`): path to write the output.
- `--min-count N` (optional, default: no filtering): only include groups
  whose `count >= N` in the output. Does not affect `skipped_rows`
  reporting. A non-integer value for `N` is a fatal error (exit `1`), same
  as any other bad CLI argument.
- `-h / --help`: print usage text.

Exit codes:

- `0`: success, including the header-only empty-input case.
- `1`: fatal error — missing/unreadable input file, input with no header
  row, unwritable output path, or a bad CLI argument. There is no separate
  exit code for argument errors; everything fatal returns `1` with a
  message on stderr.

## 8. Explicit out-of-scope

- Timezone conversion or normalisation of timestamps (treated as opaque,
  sortable strings once parsed).
- Merging or reading multiple input files in one run.
- Streaming or real-time tailing — one-shot batch run only.
- Filtering flags (by service, level, date range, etc.).
- Output formats other than CSV (e.g. JSON).
- Config file support.
- Severity ordering, thresholds, or alerting logic on `level`.
- Deduplication of identical rows beyond the grouping described in §1.

## Signed off

Onyskiu, Uladzislau (EPAM) — 2026-09-21
