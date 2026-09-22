"""Black-box tests for logsum: invoke it as a subprocess, check observable behaviour."""

import csv
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOGSUM = REPO_ROOT / "src" / "logsum.py"
FIXTURES = REPO_ROOT / "data" / "fixtures"
SAMPLE_EVENTS = REPO_ROOT / "data" / "sample_events.csv"


def run_logsum(args):
    return subprocess.run(
        [sys.executable, str(LOGSUM), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def read_output_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


HEADER = ["service", "level", "count", "first_seen", "last_seen"]


# --- Grouping and normalisation (spec sections 1, 2) ------------------------


def test_grouping_and_normalisation(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(
        ["--input", str(FIXTURES / "grouping_and_normalisation.csv"), "--output", str(output)]
    )

    assert result.returncode == 0
    rows = read_output_rows(output)
    assert rows[0] == HEADER

    data_rows = {(r[0], r[1]): r for r in rows[1:]}

    # "auth"/INFO, "auth"/info, and " auth "/INFO all collapse into one group.
    assert data_rows[("auth", "INFO")][2] == "3"
    assert data_rows[("auth", "INFO")][3] == "2026-01-01T08:00:00"
    assert data_rows[("auth", "INFO")][4] == "2026-01-01T08:10:00"

    # "Auth" (capitalised) is a distinct group from "auth" - service case is preserved.
    assert data_rows[("Auth", "INFO")][2] == "1"
    assert data_rows[("Auth", "INFO")][3] == "2026-01-01T08:15:00"
    assert data_rows[("Auth", "INFO")][4] == "2026-01-01T08:15:00"

    # "payments"/ERROR and " payments "/error collapse into one group.
    assert data_rows[("payments", "ERROR")][2] == "2"
    assert data_rows[("payments", "ERROR")][3] == "2026-01-01T09:00:00"
    assert data_rows[("payments", "ERROR")][4] == "2026-01-01T09:30:00"

    assert len(data_rows) == 3


def test_message_not_used_for_grouping_or_output(tmp_path):
    output = tmp_path / "summary.csv"
    run_logsum(["--input", str(FIXTURES / "grouping_and_normalisation.csv"), "--output", str(output)])
    rows = read_output_rows(output)
    assert rows[0] == HEADER
    for row in rows[1:]:
        assert len(row) == 5  # no message column, ever


# --- Missing level (spec section 4) -----------------------------------------


def test_missing_level_becomes_unknown_and_is_counted(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(["--input", str(FIXTURES / "missing_level.csv"), "--output", str(output)])

    assert result.returncode == 0
    rows = read_output_rows(output)
    data_rows = {(r[0], r[1]): r for r in rows[1:]}

    assert ("search", "UNKNOWN") in data_rows
    assert data_rows[("search", "UNKNOWN")][2] == "2"
    assert data_rows[("search", "UNKNOWN")][3] == "2026-01-01T10:00:00"
    assert data_rows[("search", "UNKNOWN")][4] == "2026-01-01T10:05:00"

    assert data_rows[("search", "INFO")][2] == "1"


# --- Malformed timestamps + skipped_rows (spec section 5) -------------------


def test_malformed_timestamp_excluded_but_counted_as_skipped(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(["--input", str(FIXTURES / "malformed_timestamp.csv"), "--output", str(output)])

    assert result.returncode == 0
    assert "skipped_rows: 2" in result.stderr

    rows = read_output_rows(output)
    data_rows = {(r[0], r[1]): r for r in rows[1:]}

    # The two good "auth"/INFO rows survive; the malformed row between them
    # does not affect count/first_seen/last_seen.
    assert data_rows[("auth", "INFO")][2] == "2"
    assert data_rows[("auth", "INFO")][3] == "2026-01-01T08:00:00"
    assert data_rows[("auth", "INFO")][4] == "2026-01-01T08:05:00"

    # "payments"/ERROR had only one row and it was malformed, so the whole
    # group never comes into existence.
    assert ("payments", "ERROR") not in data_rows
    assert len(data_rows) == 1


def test_all_malformed_produces_header_only_and_reports_skipped(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(["--input", str(FIXTURES / "all_malformed.csv"), "--output", str(output)])

    assert result.returncode == 0
    assert "skipped_rows: 2" in result.stderr
    rows = read_output_rows(output)
    assert rows == [HEADER]


def test_malformed_timestamp_never_crashes(tmp_path):
    result = subprocess.run(
        [sys.executable, str(LOGSUM), "--input", str(FIXTURES / "malformed_timestamp.csv")],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert result.returncode == 0


# --- Empty / header-only input (spec section 6) -----------------------------


def test_header_only_input_writes_header_and_exits_zero(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(["--input", str(FIXTURES / "header_only.csv"), "--output", str(output)])

    assert result.returncode == 0
    rows = read_output_rows(output)
    assert rows == [HEADER]


def test_completely_empty_input_is_fatal(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(["--input", str(FIXTURES / "empty.csv"), "--output", str(output)])

    assert result.returncode == 1
    assert result.stderr.strip() != ""
    assert not output.exists()


# --- CLI flags and exit codes (spec section 7) ------------------------------


def test_missing_input_file_is_fatal(tmp_path):
    missing = tmp_path / "does_not_exist.csv"
    output = tmp_path / "summary.csv"
    result = run_logsum(["--input", str(missing), "--output", str(output)])

    assert result.returncode == 1
    assert result.stderr.strip() != ""
    assert not output.exists()


def test_unwritable_output_path_is_fatal(tmp_path):
    output = tmp_path / "no_such_directory" / "summary.csv"
    result = run_logsum(["--input", str(SAMPLE_EVENTS), "--output", str(output)])

    assert result.returncode == 1
    assert result.stderr.strip() != ""


def test_missing_required_input_flag_is_fatal(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(["--output", str(output)])

    assert result.returncode == 1
    assert result.stderr.strip() != ""


def test_default_output_path(tmp_path):
    result = subprocess.run(
        [sys.executable, str(LOGSUM), "--input", str(SAMPLE_EVENTS)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert result.returncode == 0
    assert (tmp_path / "summary.csv").exists()


def test_help_flag_prints_usage_and_exits_zero():
    result = run_logsum(["-h"])
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()


def test_short_flags_i_and_o(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(["-i", str(SAMPLE_EVENTS), "-o", str(output)])
    assert result.returncode == 0
    assert output.exists()


# --- sample_events.csv end-to-end check -------------------------------------


def test_sample_events(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(["--input", str(SAMPLE_EVENTS), "--output", str(output)])

    assert result.returncode == 0
    assert "skipped_rows: 1" in result.stderr

    rows = read_output_rows(output)
    data_rows = {(r[0], r[1]): r for r in rows[1:]}

    assert data_rows[("auth", "INFO")][2] == "2"
    assert data_rows[("auth", "INFO")][3] == "2026-01-01T08:00:00"
    assert data_rows[("auth", "INFO")][4] == "2026-01-01T08:05:00"

    assert data_rows[("payments", "ERROR")][2] == "1"
    assert data_rows[("payments", "ERROR")][3] == "2026-01-01T09:00:00"
    assert data_rows[("payments", "ERROR")][4] == "2026-01-01T09:00:00"

    assert data_rows[("search", "DEBUG")][2] == "1"
    assert data_rows[("search", "DEBUG")][3] == "2026-01-01T10:00:00"

    assert data_rows[("search", "UNKNOWN")][2] == "1"
    assert data_rows[("search", "UNKNOWN")][3] == "2026-01-01T10:30:00"

    # The WARN/search row has a malformed timestamp, so no WARN group exists.
    assert ("search", "WARN") not in data_rows

    assert len(data_rows) == 4


# --- --min-count (spec section 7) -------------------------------------------


def test_min_count_filters_groups_below_threshold(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(
        [
            "--input", str(FIXTURES / "grouping_and_normalisation.csv"),
            "--output", str(output),
            "--min-count", "2",
        ]
    )

    assert result.returncode == 0
    rows = read_output_rows(output)
    groups = {(r[0], r[1]) for r in rows[1:]}

    assert ("auth", "INFO") in groups  # count 3
    assert ("payments", "ERROR") in groups  # count 2
    assert ("Auth", "INFO") not in groups  # count 1, filtered out
    assert len(groups) == 2


def test_min_count_zero_includes_everything(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(
        [
            "--input", str(FIXTURES / "grouping_and_normalisation.csv"),
            "--output", str(output),
            "--min-count", "0",
        ]
    )

    assert result.returncode == 0
    rows = read_output_rows(output)
    assert len(rows) - 1 == 3  # all three groups present


def test_min_count_does_not_affect_skipped_rows_reporting(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(
        [
            "--input", str(FIXTURES / "malformed_timestamp.csv"),
            "--output", str(output),
            "--min-count", "100",
        ]
    )

    assert result.returncode == 0
    assert "skipped_rows: 2" in result.stderr
    rows = read_output_rows(output)
    assert rows == [HEADER]  # every group filtered out by the high threshold


def test_min_count_non_integer_is_fatal(tmp_path):
    output = tmp_path / "summary.csv"
    result = run_logsum(
        [
            "--input", str(SAMPLE_EVENTS),
            "--output", str(output),
            "--min-count", "not-a-number",
        ]
    )

    assert result.returncode == 1
    assert result.stderr.strip() != ""
    assert not output.exists()
