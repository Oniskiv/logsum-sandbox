"""logsum: summarise synthetic events.csv logs into per-(service, level) counts.

Usage:
    logsum --input events.csv --output summary.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

DEFAULT_OUTPUT = "summary.csv"
UNKNOWN_LEVEL = "UNKNOWN"
OUTPUT_HEADER = ["service", "level", "count", "first_seen", "last_seen"]


class GroupKey(NamedTuple):
    service: str
    level: str


class GroupStats:
    """Running count/first_seen/last_seen for a single (service, level) group."""

    def __init__(self, timestamp: datetime, raw_timestamp: str) -> None:
        self.count = 1
        self._first_seen_ts = timestamp
        self._last_seen_ts = timestamp
        self.first_seen = raw_timestamp
        self.last_seen = raw_timestamp

    def add(self, timestamp: datetime, raw_timestamp: str) -> None:
        self.count += 1
        if timestamp < self._first_seen_ts:
            self._first_seen_ts = timestamp
            self.first_seen = raw_timestamp
        if timestamp > self._last_seen_ts:
            self._last_seen_ts = timestamp
            self.last_seen = raw_timestamp


class LogsumError(Exception):
    """A fatal, user-facing error that should exit with status 1."""


class ArgumentParserExitOne(argparse.ArgumentParser):
    """argparse exits with status 2 on bad arguments; the spec requires 1."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = ArgumentParserExitOne(
        prog="logsum",
        description="Summarise events.csv logs by (service, level).",
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="path to the input events.csv",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"path to write the output (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=None,
        metavar="N",
        help="only include groups whose count >= N",
    )
    return parser


def normalise_service(value: str | None) -> str:
    return (value or "").strip()


def normalise_level(value: str | None) -> str:
    stripped = (value or "").strip()
    return stripped.upper() if stripped else UNKNOWN_LEVEL


def parse_timestamp(raw_value: str | None) -> datetime:
    """Parse a timestamp, raising ValueError if it is malformed or missing."""
    return datetime.fromisoformat((raw_value or "").strip())


def read_rows(input_path: Path) -> list[dict[str, str | None]]:
    """Read the input CSV, returning its data rows.

    Raises LogsumError if the file can't be opened or has no header row at
    all (a completely empty file), per spec section 6.
    """
    try:
        with open(input_path, newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise LogsumError(
                    f"input file '{input_path}' is empty (no header row)"
                )
            return list(reader)
    except OSError as exc:
        raise LogsumError(f"cannot read input file '{input_path}': {exc}") from exc


def aggregate(
    rows: list[dict[str, str | None]],
) -> tuple[dict[GroupKey, GroupStats], int]:
    """Group rows by (service, level), skipping rows with malformed timestamps.

    Returns the groups (in first-seen-group-first order) and a count of
    skipped rows.
    """
    groups: dict[GroupKey, GroupStats] = {}
    skipped_rows = 0

    for row in rows:
        raw_timestamp = row.get("timestamp") or ""
        try:
            timestamp = parse_timestamp(raw_timestamp)
        except ValueError:
            skipped_rows += 1
            continue

        key = GroupKey(
            service=normalise_service(row.get("service")),
            level=normalise_level(row.get("level")),
        )
        existing = groups.get(key)
        if existing is None:
            groups[key] = GroupStats(timestamp, raw_timestamp)
        else:
            existing.add(timestamp, raw_timestamp)

    return groups, skipped_rows


def filter_groups(
    groups: dict[GroupKey, GroupStats],
    min_count: int | None,
) -> dict[GroupKey, GroupStats]:
    """Apply the --min-count threshold (spec section 7), keeping insertion order."""
    if min_count is None:
        return groups
    return {key: stats for key, stats in groups.items() if stats.count >= min_count}


def write_summary(output_path: Path, groups: dict[GroupKey, GroupStats]) -> None:
    try:
        with open(output_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(OUTPUT_HEADER)
            for key, stats in groups.items():
                writer.writerow(
                    [key.service, key.level, stats.count, stats.first_seen, stats.last_seen]
                )
    except OSError as exc:
        raise LogsumError(f"cannot write output file '{output_path}': {exc}") from exc


def run(args: argparse.Namespace) -> int:
    rows = read_rows(Path(args.input))
    groups, skipped_rows = aggregate(rows)
    write_summary(Path(args.output), filter_groups(groups, args.min_count))
    print(f"skipped_rows: {skipped_rows}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except LogsumError as exc:
        print(f"logsum: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
