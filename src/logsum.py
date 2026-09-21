"""Summarise events.csv into per-(service, level) group stats. See spec.md."""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REQUIRED_COLUMNS = ("timestamp", "level", "service", "message")


def normalise_service(raw: str | None) -> str:
    return (raw or "").strip()


def normalise_level(raw: str | None) -> str:
    text = (raw or "").strip()
    return text.upper() if text else "UNKNOWN"


def parse_timestamp(raw: str | None) -> datetime:
    if raw is None:
        raise ValueError("missing timestamp")
    return datetime.fromisoformat(raw.strip())


@dataclass
class _GroupStats:
    count: int
    first_seen: str
    first_seen_dt: datetime
    last_seen: str
    last_seen_dt: datetime

    def update(self, raw_ts: str, ts: datetime) -> None:
        self.count += 1
        if ts < self.first_seen_dt:
            self.first_seen, self.first_seen_dt = raw_ts, ts
        if ts > self.last_seen_dt:
            self.last_seen, self.last_seen_dt = raw_ts, ts


def summarise(reader: csv.DictReader) -> tuple[dict[tuple[str, str], dict], int]:
    groups: dict[tuple[str, str], _GroupStats] = {}
    skipped = 0
    for row in reader:
        raw_ts = row.get("timestamp")
        try:
            ts = parse_timestamp(raw_ts)
        except ValueError:
            skipped += 1
            continue
        key = (normalise_service(row.get("service")), normalise_level(row.get("level")))
        if key in groups:
            groups[key].update(raw_ts, ts)
        else:
            groups[key] = _GroupStats(
                count=1, first_seen=raw_ts, first_seen_dt=ts, last_seen=raw_ts, last_seen_dt=ts
            )
    return (
        {
            key: {"count": s.count, "first_seen": s.first_seen, "last_seen": s.last_seen}
            for key, s in groups.items()
        },
        skipped,
    )


def write_summary(path: Path, groups: dict[tuple[str, str], dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["service", "level", "count", "first_seen", "last_seen"])
        for (service, level), stats in groups.items():
            writer.writerow(
                [service, level, stats["count"], stats["first_seen"], stats["last_seen"]]
            )


def run(input_path: Path, output_path: Path) -> int:
    try:
        input_file = input_path.open("r", newline="", encoding="utf-8")
    except OSError as exc:
        print(f"logsum: cannot read {input_path}: {exc}", file=sys.stderr)
        return 1

    with input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            print(f"logsum: {input_path} has no header row", file=sys.stderr)
            return 1
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            print(
                f"logsum: {input_path} missing required column(s): {', '.join(missing)}",
                file=sys.stderr,
            )
            return 1
        groups, skipped = summarise(reader)

    try:
        write_summary(output_path, groups)
    except OSError as exc:
        print(f"logsum: cannot write {output_path}: {exc}", file=sys.stderr)
        return 1

    if skipped:
        print(f"logsum: skipped {skipped} row(s) with malformed timestamps", file=sys.stderr)
    return 0


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="logsum",
        description="Summarise events.csv into per-(service, level) group stats.",
    )
    parser.add_argument("-i", "--input", required=True, help="path to the input events.csv")
    parser.add_argument(
        "-o", "--output", default="summary.csv", help="path to write the output (default: summary.csv)"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    return run(Path(args.input), Path(args.output))


if __name__ == "__main__":
    sys.exit(main())
