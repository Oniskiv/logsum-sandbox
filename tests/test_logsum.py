"""Tests for the logsum CLI, derived from spec.md only.

The CLI under test (src/logsum.py) is deliberately treated as a black box:
it is only ever invoked as a subprocess. Section numbers in test/comment
names refer to spec.md sections.
"""
import csv
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "src" / "logsum.py"
FIXTURES = REPO_ROOT / "data" / "fixtures"

EXPECTED_HEADER = ["service", "level", "count", "first_seen", "last_seen"]


def run_cli(*args, cwd=None):
    cmd = [sys.executable, str(SCRIPT), *args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, check=False)


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_header(path):
    with open(path, newline="", encoding="utf-8") as f:
        return next(csv.reader(f))


def as_comparable(rows):
    return {
        (r["service"], r["level"]): (
            int(r["count"]),
            r["first_seen"],
            r["last_seen"],
        )
        for r in rows
    }


# --- 1. Exact group key: (service, level), message excluded ---------------


def test_grouping_uses_service_and_level_only(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "grouping_and_normalisation.csv"), "-o", str(out))

    assert result.returncode == 0
    rows = read_rows(out)
    groups = as_comparable(rows)

    # Three different messages within (auth, INFO) still collapse into one group.
    assert groups[("auth", "INFO")] == (3, "2026-01-01T08:00:00", "2026-01-01T08:10:00")


def test_message_column_is_not_part_of_output(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "grouping_and_normalisation.csv"), "-o", str(out))

    assert result.returncode == 0
    assert "message" not in read_header(out)


# --- 2. Normalisation rules -------------------------------------------------


def test_service_whitespace_is_stripped_but_case_is_preserved(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "grouping_and_normalisation.csv"), "-o", str(out))

    assert result.returncode == 0
    groups = as_comparable(read_rows(out))

    # " auth " merges into "auth" (whitespace stripped) ...
    assert groups[("auth", "INFO")][0] == 3
    # ... but "Auth" (different case) stays a separate group (case preserved).
    assert ("Auth", "INFO") in groups
    assert groups[("Auth", "INFO")] == (1, "2026-01-01T08:15:00", "2026-01-01T08:15:00")


def test_level_whitespace_and_case_collapse_to_same_group(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "grouping_and_normalisation.csv"), "-o", str(out))

    assert result.returncode == 0
    groups = as_comparable(read_rows(out))

    # "ERROR" and "error" (with surrounding whitespace on service) collapse together.
    assert groups[("payments", "ERROR")] == (2, "2026-01-01T09:00:00", "2026-01-01T09:30:00")
    # Levels are uppercased in the output.
    assert all(level == level.upper() for (_, level) in groups)


# --- 3. count / first_seen / last_seen + exact header ----------------------


def test_summary_header_is_exact(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "grouping_and_normalisation.csv"), "-o", str(out))

    assert result.returncode == 0
    assert read_header(out) == EXPECTED_HEADER


def test_first_seen_and_last_seen_are_min_and_max_verbatim(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "grouping_and_normalisation.csv"), "-o", str(out))

    assert result.returncode == 0
    groups = as_comparable(read_rows(out))
    count, first_seen, last_seen = groups[("auth", "INFO")]
    assert count == 3
    # Verbatim input format, no reformatting.
    assert first_seen == "2026-01-01T08:00:00"
    assert last_seen == "2026-01-01T08:10:00"


# --- 4. Missing level behaviour ---------------------------------------------


def test_blank_and_whitespace_only_level_become_unknown(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "missing_level.csv"), "-o", str(out))

    assert result.returncode == 0
    groups = as_comparable(read_rows(out))

    assert groups[("search", "UNKNOWN")] == (2, "2026-01-01T10:00:00", "2026-01-01T10:05:00")
    assert groups[("search", "INFO")] == (1, "2026-01-01T10:10:00", "2026-01-01T10:10:00")


def test_missing_level_rows_are_counted_not_dropped(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "missing_level.csv"), "-o", str(out))

    assert result.returncode == 0
    total = sum(int(r["count"]) for r in read_rows(out))
    assert total == 3  # all 3 input rows accounted for


# --- 5. Malformed timestamp behaviour ---------------------------------------


def test_malformed_timestamp_excluded_from_aggregation(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "malformed_timestamp.csv"), "-o", str(out))

    assert result.returncode == 0
    groups = as_comparable(read_rows(out))

    # Only the 2 valid auth/INFO rows are aggregated.
    assert groups[("auth", "INFO")] == (2, "2026-01-01T08:00:00", "2026-01-01T08:05:00")
    # Spec §5 only guarantees malformed rows don't perturb an existing group's
    # count/first_seen/last_seen. It does not say whether a (service, level)
    # pair whose *only* rows are malformed is omitted entirely or appears with
    # count=0 -- that's a genuine spec ambiguity (see test-notes.md), so accept
    # either reading here instead of asserting the implementation's choice.
    if ("payments", "ERROR") in groups:
        assert groups[("payments", "ERROR")][0] == 0


def test_malformed_timestamp_is_tallied_in_skipped_rows_on_stderr(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "malformed_timestamp.csv"), "-o", str(out))

    assert result.returncode == 0
    assert re.search(r"skip\w*\D*2\b", result.stderr, re.IGNORECASE)


def test_malformed_timestamp_never_crashes_the_cli(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "malformed_timestamp.csv"), "-o", str(out))

    assert result.returncode == 0
    assert out.exists()


def test_all_rows_malformed_still_produces_a_valid_summary(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "all_malformed.csv"), "-o", str(out))

    assert result.returncode == 0
    assert read_header(out) == EXPECTED_HEADER
    # Spec doesn't settle whether groups with no valid rows are omitted or
    # listed with count=0 -- see test-notes.md. Either is acceptable here;
    # what matters is no malformed row is ever counted.
    rows = read_rows(out)
    assert rows == [] or all(int(r["count"]) == 0 for r in rows)
    assert re.search(r"skip\w*\D*2\b", result.stderr, re.IGNORECASE)


# --- 6. Empty input behaviour -------------------------------------------------


def test_header_only_input_writes_header_only_output_and_exits_0(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "header_only.csv"), "-o", str(out))

    assert result.returncode == 0
    assert out.exists()
    assert read_header(out) == EXPECTED_HEADER
    assert read_rows(out) == []


def test_completely_empty_input_is_a_fatal_error(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "empty.csv"), "-o", str(out))

    assert result.returncode == 1
    assert result.stderr.strip() != ""


# --- 7. CLI flags and exit codes --------------------------------------------


def test_missing_input_file_is_fatal_error(tmp_path):
    missing = tmp_path / "does_not_exist.csv"
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(missing), "-o", str(out))

    assert result.returncode == 1
    assert result.stderr.strip() != ""
    assert not out.exists()


@pytest.mark.parametrize(
    "bad_output",
    [
        "no_such_dir/summary.csv",  # parent directory doesn't exist
        ".",  # a directory, not a file
    ],
)
def test_unwritable_output_path_is_fatal_error(tmp_path, bad_output):
    out = tmp_path / bad_output
    result = run_cli(
        "-i", str(FIXTURES / "header_only.csv"), "-o", str(out), cwd=str(tmp_path)
    )

    assert result.returncode == 1
    assert result.stderr.strip() != ""


def test_unknown_cli_argument_is_fatal_error_exit_1(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli(
        "-i", str(FIXTURES / "header_only.csv"), "-o", str(out), "--bogus-flag"
    )

    # Spec: no separate exit code for argument errors -- everything fatal is 1,
    # not argparse's usual 2.
    assert result.returncode == 1


def test_missing_required_input_argument_is_fatal_error_exit_1():
    result = run_cli()

    assert result.returncode == 1


def test_help_flag_prints_usage_and_exits_0():
    result = run_cli("-h")

    assert result.returncode == 0
    combined = (result.stdout + result.stderr).lower()
    assert "usage" in combined
    assert "--input" in combined


def test_output_defaults_to_summary_csv_in_current_directory(tmp_path):
    result = run_cli("-i", str(FIXTURES / "header_only.csv"), cwd=str(tmp_path))

    assert result.returncode == 0
    default_out = tmp_path / "summary.csv"
    assert default_out.exists()
    assert read_header(default_out) == EXPECTED_HEADER


def test_explicit_output_option_is_honoured(tmp_path):
    out = tmp_path / "custom_name.csv"
    result = run_cli("-i", str(FIXTURES / "header_only.csv"), "-o", str(out))

    assert result.returncode == 0
    assert out.exists()


def test_help_flag_mentions_min_count():
    result = run_cli("-h")

    assert result.returncode == 0
    combined = (result.stdout + result.stderr).lower()
    assert "--min-count" in combined


# --- 9. --min-count filtering -----------------------------------------------


def test_min_count_filters_out_smaller_groups(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli(
        "-i", str(FIXTURES / "grouping_and_normalisation.csv"), "-o", str(out), "--min-count", "2"
    )

    assert result.returncode == 0
    groups = as_comparable(read_rows(out))

    assert ("auth", "INFO") in groups
    assert ("payments", "ERROR") in groups
    assert ("Auth", "INFO") not in groups


def test_min_count_zero_keeps_all_groups(tmp_path):
    default_out = tmp_path / "default.csv"
    zero_out = tmp_path / "zero.csv"
    default_result = run_cli(
        "-i", str(FIXTURES / "grouping_and_normalisation.csv"), "-o", str(default_out)
    )
    zero_result = run_cli(
        "-i", str(FIXTURES / "grouping_and_normalisation.csv"), "-o", str(zero_out),
        "--min-count", "0",
    )

    assert default_result.returncode == 0
    assert zero_result.returncode == 0
    assert as_comparable(read_rows(default_out)) == as_comparable(read_rows(zero_out))


def test_default_behaviour_unchanged_without_min_count_flag(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli("-i", str(FIXTURES / "grouping_and_normalisation.csv"), "-o", str(out))

    assert result.returncode == 0
    groups = as_comparable(read_rows(out))

    assert ("auth", "INFO") in groups
    assert ("Auth", "INFO") in groups
    assert ("payments", "ERROR") in groups


def test_min_count_on_header_only_input_still_exits_0(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli(
        "-i", str(FIXTURES / "header_only.csv"), "-o", str(out), "--min-count", "5"
    )

    assert result.returncode == 0
    assert read_header(out) == EXPECTED_HEADER
    assert read_rows(out) == []


def test_non_integer_min_count_is_fatal_error_exit_1(tmp_path):
    out = tmp_path / "summary.csv"
    result = run_cli(
        "-i", str(FIXTURES / "header_only.csv"), "-o", str(out), "--min-count", "abc"
    )

    assert result.returncode == 1
