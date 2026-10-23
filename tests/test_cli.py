"""Installed invocation and operational exit codes around the existing run contract."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import astropy.units as u
import pytest
from astropy.time import Time
from astropy.utils import iers

import spacecraft_mission_analysis.cli as cli

EXAMPLE = Path(__file__).parent.parent / "examples" / "vanguard_run"
CONFIG = EXAMPLE / "config.json"
SAVED = json.loads((EXAMPLE / "run.json").read_text(encoding="utf-8"))
CSV_NAMES = {
    "run.csv",
    "stations.csv",
    "access_windows.csv",
    "coverage.csv",
    "union_intervals.csv",
    "warnings.csv",
}


def _write_config(directory: Path, **changes: object) -> Path:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    data.update(changes)
    path = directory / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _configured_iers(directory: Path, **changes: object) -> Path:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    data["earth_orientation_mode"] = "configured_iers"
    data["earth_orientation_source"] = "Astropy configured IERS table"
    del data["earth_orientation_table_file"]
    data.update(changes)
    path = directory / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _assert_archived_science(actual: dict) -> None:
    assert actual["status"] == SAVED["status"] == "SUCCESS"
    assert actual["configuration"] == SAVED["configuration"]
    assert actual["provenance"] == SAVED["provenance"]
    assert actual["coverage"] == SAVED["coverage"]
    assert actual["notices"] == SAVED["notices"] == []
    assert len(actual["station_access"]) == len(SAVED["station_access"])
    for station, saved_station in zip(actual["station_access"], SAVED["station_access"]):
        assert station["station_name"] == saved_station["station_name"]
        assert len(station["windows"]) == len(saved_station["windows"])
        for window, saved_window in zip(station["windows"], saved_station["windows"]):
            assert abs(window["max_elevation_deg"] - saved_window["max_elevation_deg"]) <= 1e-5
            current_time = Time(window["max_elevation_time_utc"].removesuffix("Z"), scale="utc")
            saved_time = Time(saved_window["max_elevation_time_utc"].removesuffix("Z"), scale="utc")
            assert abs((current_time - saved_time).to_value(u.s)) <= 0.02
            assert {
                key: value
                for key, value in window.items()
                if key not in {"max_elevation_deg", "max_elevation_time_utc"}
            } == {
                key: value
                for key, value in saved_window.items()
                if key not in {"max_elevation_deg", "max_elevation_time_utc"}
            }


def test_canonical_cli_run_writes_complete_archived_result(tmp_path: Path, capsys) -> None:
    output = tmp_path / "result"
    assert cli.main([str(CONFIG), "--output-dir", str(output)]) == 0
    assert {item.name for item in output.iterdir()} == {"run.json", "report.html", "csv"}
    assert {item.name for item in (output / "csv").iterdir()} == CSV_NAMES
    _assert_archived_science(json.loads((output / "run.json").read_text(encoding="utf-8")))
    report = (output / "report.html").read_text(encoding="utf-8")
    assert "Access timeline" in report
    assert "51.22%" in report
    assert "Geometric station access" in report
    stdout = capsys.readouterr().out
    for item in (
        "status=SUCCESS",
        "stations=2",
        "station_access_windows=2",
        "merged_coverage_intervals=1",
        "coverage_fraction=0.512195008791",
        "warnings=0",
    ):
        assert item in stdout


def test_invalid_tle_config_returns_two_without_analysis(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    line = json.loads(CONFIG.read_text(encoding="utf-8"))["tle_line1"]
    bad = _write_config(tmp_path, tle_line1=line[:-1] + ("0" if line[-1] != "0" else "1"))
    output = tmp_path / "result"

    def unexpected_analysis(_config):
        pytest.fail("invalid input reached scientific analysis")

    monkeypatch.setattr(cli, "run_analysis", unexpected_analysis)
    assert cli.main([str(bad), "--output-dir", str(output)]) == 2
    assert not output.exists()
    assert "input error:" in capsys.readouterr().err


def test_escaped_surrogate_is_rejected_before_analysis(tmp_path: Path, monkeypatch, capsys) -> None:
    config = _write_config(tmp_path, source_revision="\ud800")
    assert b"\\ud800" in config.read_bytes()
    output = tmp_path / "result"

    def unexpected_analysis(_config):
        pytest.fail("invalid Unicode reached scientific analysis")

    monkeypatch.setattr(cli, "run_analysis", unexpected_analysis)
    assert cli.main([str(config), "--output-dir", str(output)]) == 2
    assert not output.exists()
    stderr = capsys.readouterr().err
    assert "source_revision must contain valid Unicode scalar text" in stderr
    assert "Traceback" not in stderr

    name = "spacecraft-mission-analysis.exe" if os.name == "nt" else "spacecraft-mission-analysis"
    command = Path(sys.executable).parent / name
    completed = subprocess.run(
        [str(command), str(config), "--output-dir", str(output)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 2
    assert "source_revision must contain valid Unicode scalar text" in completed.stderr
    assert "Traceback" not in completed.stderr
    assert not output.exists()


@pytest.mark.parametrize("collection", ["stations", "windows"])
def test_archived_comparison_rejects_truncated_collection(collection: str) -> None:
    actual = deepcopy(SAVED)
    if collection == "stations":
        actual["station_access"].pop()
    else:
        actual["station_access"][0]["windows"].pop()
    with pytest.raises(AssertionError):
        _assert_archived_science(actual)


def test_legitimate_stale_tle_warning_returns_zero_and_is_exported(tmp_path: Path, capsys) -> None:
    config = _configured_iers(
        tmp_path,
        analysis_start_utc="2000-07-05T20:00:00Z",
        analysis_end_utc="2000-07-05T20:10:00Z",
        coarse_step_s=60,
    )
    output = tmp_path / "result"
    with iers.conf.set_temp("auto_download", False):
        assert cli.main([str(config), "--output-dir", str(output)]) == 0
    data = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert data["status"] == "SUCCESS_WITH_WARNINGS"
    assert [notice["code"] for notice in data["notices"]] == ["TLE_AGE_WARNING"]
    stdout = capsys.readouterr().out
    assert "status=SUCCESS_WITH_WARNINGS" in stdout
    assert "TLE_AGE_WARNING:" in stdout


def test_scientific_failure_writes_structured_result_and_returns_three(
    tmp_path: Path, capsys
) -> None:
    config = _configured_iers(tmp_path)
    unavailable = iers.IERS(
        {
            "MJD": [53000, 53001] * u.day,
            "UT1_UTC": [0.0, 0.0] * u.s,
            "PM_x": [0.0, 0.0] * u.arcsec,
            "PM_y": [0.0, 0.0] * u.arcsec,
        }
    )
    output = tmp_path / "result"
    with iers.conf.set_temp("auto_download", False), iers.earth_orientation_table.set(unavailable):
        assert cli.main([str(config), "--output-dir", str(output)]) == 3
    data = json.loads((output / "run.json").read_text(encoding="utf-8"))
    assert data["status"] == "FAILED"
    assert data["coverage"] is data["station_access"] is None
    assert data["notices"][-1]["code"] == "EOP_UNAVAILABLE"
    assert {item.name for item in (output / "csv").iterdir()} == CSV_NAMES
    report = (output / "report.html").read_text(encoding="utf-8")
    assert "No access or coverage results were produced" in report
    assert "EOP_UNAVAILABLE" in report
    assert "<svg" not in report
    assert "EOP_UNAVAILABLE:" in capsys.readouterr().err


def test_existing_artifact_is_untouched_and_no_bundle_is_published(tmp_path: Path, capsys) -> None:
    output = tmp_path / "result"
    (output / "csv").mkdir(parents=True)
    conflict = output / "csv" / "run.csv"
    conflict.write_bytes(b"existing evidence\n")
    assert cli.main([str(CONFIG), "--output-dir", str(output)]) == 4
    assert conflict.read_bytes() == b"existing evidence\n"
    assert {item.name for item in (output / "csv").iterdir()} == {"run.csv"}
    assert not (output / "run.json").exists()
    assert not (output / "report.html").exists()
    assert str(conflict) in capsys.readouterr().err


def test_existing_report_is_untouched_and_blocks_bundle(tmp_path: Path, capsys) -> None:
    output = tmp_path / "result"
    output.mkdir()
    report = output / "report.html"
    report.write_bytes(b"existing report\n")
    assert cli.main([str(CONFIG), "--output-dir", str(output)]) == 4
    assert report.read_bytes() == b"existing report\n"
    assert not (output / "run.json").exists()
    assert "report.html" in capsys.readouterr().err


def test_missing_config_returns_two_without_output(tmp_path: Path, capsys) -> None:
    output = tmp_path / "result"
    assert cli.main([str(tmp_path / "missing.json"), "--output-dir", str(output)]) == 2
    assert not output.exists()
    assert "input error:" in capsys.readouterr().err


def test_output_directory_as_file_returns_four(tmp_path: Path, capsys) -> None:
    output = tmp_path / "result"
    output.write_bytes(b"keep me")
    assert cli.main([str(CONFIG), "--output-dir", str(output)]) == 4
    assert output.read_bytes() == b"keep me"
    assert "output error:" in capsys.readouterr().err


def test_output_write_failure_leaves_no_analysis_artifacts(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    def fail_write(_result, _directory):
        raise OSError("simulated storage failure")

    monkeypatch.setattr(cli, "write_csv_bundle", fail_write)
    output = tmp_path / "result"
    assert cli.main([str(CONFIG), "--output-dir", str(output)]) == 4
    assert not (output / "run.json").exists()
    assert not (output / "report.html").exists()
    assert not list((output / "csv").iterdir())
    assert "simulated storage failure" in capsys.readouterr().err


def test_publication_failure_rolls_back_new_artifacts(tmp_path: Path, monkeypatch) -> None:
    original_copy = cli.shutil.copyfileobj
    calls = 0

    def fail_second_copy(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated publication failure")
        return original_copy(source, target)

    monkeypatch.setattr(cli.shutil, "copyfileobj", fail_second_copy)
    output = tmp_path / "result"
    assert cli.main([str(CONFIG), "--output-dir", str(output)]) == 4
    assert not (output / "run.json").exists()
    assert not (output / "report.html").exists()
    assert not list((output / "csv").iterdir())


def test_argparse_usage_error_returns_two_without_analysis(capsys) -> None:
    assert cli.main([str(CONFIG)]) == 2
    assert "--output-dir" in capsys.readouterr().err


def test_unexpected_analysis_defect_is_not_mapped_to_operational_exit(
    tmp_path: Path, monkeypatch
) -> None:
    def defect(_config):
        raise RuntimeError("programming defect")

    monkeypatch.setattr(cli, "run_analysis", defect)
    with pytest.raises(RuntimeError, match="programming defect"):
        cli.main([str(CONFIG), "--output-dir", str(tmp_path / "result")])


def test_installed_console_script_runs_from_another_working_directory(tmp_path: Path) -> None:
    name = "spacecraft-mission-analysis.exe" if os.name == "nt" else "spacecraft-mission-analysis"
    command = Path(sys.executable).parent / name
    assert command.is_file(), f"installed console script missing: {command}"
    output = tmp_path / "result"
    completed = subprocess.run(
        [str(command), str(CONFIG.resolve()), "--output-dir", str(output)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "status=SUCCESS" in completed.stdout
    _assert_archived_science(json.loads((output / "run.json").read_text(encoding="utf-8")))
    assert {item.name for item in (output / "csv").iterdir()} == CSV_NAMES
    assert (output / "report.html").is_file()
