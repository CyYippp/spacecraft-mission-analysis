"""MA-05/06 run contract, deterministic exports, and fail-closed paths."""

import csv
import io
import json
import re
from pathlib import Path

import astropy.units as u
import pytest
from astropy.time import Time
from astropy.utils import iers

import spacecraft_mission_analysis.frames as frame_module
import spacecraft_mission_analysis.run as run_module
from spacecraft_mission_analysis import (
    AnalysisConfig,
    GroundStation,
    RunStatus,
    Sgp4Propagator,
    TleRecord,
    csv_bundle,
    result_dict,
    run_analysis,
    serialize_json,
    write_csv_bundle,
    write_json,
)

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "examples" / "vanguard_run" / "config.json").read_text(
        encoding="utf-8"
    )
)
EXAMPLE = Path(__file__).parent.parent / "examples" / "vanguard_run"
TEST_EOP = json.loads((EXAMPLE / "test_only_eop.json").read_text(encoding="utf-8"))
# Existing MA-04 analytic peak criteria, frozen before the archived peak was
# evaluated. They guard platform-sensitive optimizer outputs in this snapshot.
PEAK_TIME_LIMIT_S = 0.02
PEAK_ELEVATION_LIMIT_DEG = 1e-5


def without_peak_bytes(payload: bytes, expected_windows: int) -> bytes:
    """Mask only the two optimizer-derived fields, preserving every other byte."""
    result, elevation_count = re.subn(
        rb'("max_elevation_deg": )[-+0-9.eE]+',
        rb"\1<optimizer-peak>",
        payload,
    )
    result, time_count = re.subn(
        rb'("max_elevation_time_utc": ")[^"]+',
        rb"\1<optimizer-peak>",
        result,
    )
    assert elevation_count == time_count == expected_windows
    return result


def assert_peak_snapshot_bounds(actual: dict, saved: dict) -> None:
    assert len(actual["station_access"]) == len(saved["station_access"])
    for actual_station, saved_station in zip(actual["station_access"], saved["station_access"]):
        assert actual_station["station_name"] == saved_station["station_name"]
        assert len(actual_station["windows"]) == len(saved_station["windows"])
        for actual_window, saved_window in zip(actual_station["windows"], saved_station["windows"]):
            assert (
                abs(actual_window["max_elevation_deg"] - saved_window["max_elevation_deg"])
                <= PEAK_ELEVATION_LIMIT_DEG
            )
            actual_time = Time(
                actual_window["max_elevation_time_utc"].removesuffix("Z"), scale="utc"
            )
            saved_time = Time(saved_window["max_elevation_time_utc"].removesuffix("Z"), scale="utc")
            assert abs((actual_time - saved_time).to_value(u.s)) <= PEAK_TIME_LIMIT_S


def config(
    *,
    start: Time | None = None,
    end: Time | None = None,
    minimum_elevation_deg: float = 10.0,
    coarse_step_s: float = 5.0,
    stations: tuple[GroundStation, ...] | None = None,
    earth_orientation_source: str | None = None,
) -> AnalysisConfig:
    tle = TleRecord.from_lines(
        FIXTURE["tle_line1"], FIXTURE["tle_line2"], source=FIXTURE["tle_source"]
    )
    selected_start = (
        start if start is not None else Time(FIXTURE["analysis_start_utc"], scale="utc")
    )
    selected_end = end if end is not None else Time(FIXTURE["analysis_end_utc"], scale="utc")
    if earth_orientation_source is None:
        earth_orientation_source = (
            FIXTURE["earth_orientation_source"]
            if selected_start == Time(FIXTURE["analysis_start_utc"], scale="utc")
            and selected_end == Time(FIXTURE["analysis_end_utc"], scale="utc")
            else "test-only synthetic zero EOP table spanning the requested interval"
        )
    return AnalysisConfig(
        tle,
        selected_start,
        selected_end,
        stations or tuple(GroundStation(**item) for item in FIXTURE["stations"]),
        minimum_elevation_deg=minimum_elevation_deg,
        coarse_step_s=coarse_step_s,
        root_tolerance_s=FIXTURE["root_tolerance_s"],
        earth_orientation_source=earth_orientation_source,
    )


def eop_table(start: Time, end: Time):
    first = int(start.mjd) - 1
    last = int(end.mjd) + 2
    days = list(range(first, last + 1))
    zeros = [0.0] * len(days)
    return iers.IERS(
        {
            "MJD": days * u.day,
            "UT1_UTC": zeros * u.s,
            "PM_x": zeros * u.arcsec,
            "PM_y": zeros * u.arcsec,
        }
    )


def run_with_eop(run_config: AnalysisConfig):
    if run_config.earth_orientation_source == FIXTURE["earth_orientation_source"]:
        values = TEST_EOP
        table = iers.IERS(
            {
                "MJD": values["mjd"] * u.day,
                "UT1_UTC": values["ut1_minus_utc_s"] * u.s,
                "PM_x": values["xp_arcsec"] * u.arcsec,
                "PM_y": values["yp_arcsec"] * u.arcsec,
            }
        )
    else:
        table = eop_table(run_config.start, run_config.end)
    with iers.conf.set_temp("auto_download", False), iers.earth_orientation_table.set(table):
        return run_analysis(run_config)


def rows(content: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content)))


def test_archived_clean_run_is_byte_identical_and_complete(tmp_path: Path) -> None:
    first = run_with_eop(config())
    second = run_with_eop(config())
    assert first.status == second.status == RunStatus.SUCCESS
    assert first.notices == second.notices == ()
    assert [len(item.windows) for item in first.station_access] == [1, 1]
    assert first.coverage.access_window_count == 1
    assert first.coverage.total_access_duration_s == pytest.approx(1229.2680210995704, abs=1e-6)
    assert serialize_json(first).encode() == serialize_json(second).encode()
    assert csv_bundle(first) == csv_bundle(second)

    json_a = write_json(first, tmp_path / "a" / "run.json")
    json_b = write_json(second, tmp_path / "b" / "run.json")
    csv_a = write_csv_bundle(first, tmp_path / "a" / "csv")
    csv_b = write_csv_bundle(second, tmp_path / "b" / "csv")
    assert json_a.read_bytes() == json_b.read_bytes()
    assert csv_a.keys() == csv_b.keys()
    assert all(csv_a[name].read_bytes() == csv_b[name].read_bytes() for name in csv_a)
    actual_json = json_a.read_bytes()
    saved_json = (EXAMPLE / "run.json").read_bytes()
    assert_peak_snapshot_bounds(json.loads(actual_json), json.loads(saved_json))
    window_count = sum(len(item.windows) for item in first.station_access)
    assert without_peak_bytes(actual_json, window_count) == without_peak_bytes(
        saved_json, window_count
    )
    for name, path in csv_a.items():
        actual_csv = path.read_bytes()
        saved_csv = (EXAMPLE / "csv" / name).read_bytes()
        if name != "access_windows.csv":
            assert actual_csv == saved_csv
            continue
        assert actual_csv.splitlines(keepends=True)[0] == saved_csv.splitlines(keepends=True)[0]
        assert b"\r" not in actual_csv and actual_csv.endswith(b"\n")
        actual_rows = rows(actual_csv.decode("utf-8"))
        saved_rows = rows(saved_csv.decode("utf-8"))
        assert len(actual_rows) == len(saved_rows) == window_count
        for actual_row, saved_row in zip(actual_rows, saved_rows):
            actual_row["max_elevation_deg"] = saved_row["max_elevation_deg"]
            actual_row["max_elevation_time_utc"] = saved_row["max_elevation_time_utc"]
            assert actual_row == saved_row

    data = result_dict(first)
    assert set(data) == {
        "schema_version",
        "status",
        "configuration",
        "provenance",
        "notices",
        "station_access",
        "coverage",
    }
    assert data["schema_version"] == "1.0"
    assert data["configuration"]["tle"]["line1"] == FIXTURE["tle_line1"]
    assert data["configuration"]["tle"]["line2"] == FIXTURE["tle_line2"]
    assert data["configuration"]["tle"]["source"] == FIXTURE["tle_source"]
    assert data["configuration"]["tle_age_warning_days"] == 7.0
    assert data["configuration"]["validated_analysis_span_max_hours"] == 24.0
    assert data["configuration"]["peak_refinement_xatol_s"] == 0.002
    assert data["configuration"]["earth_orientation_source"] == FIXTURE["earth_orientation_source"]
    assert data["provenance"]["sgp4_gravity_constants"] == "WGS72"
    assert data["provenance"]["station_ellipsoid"] == "WGS84"
    assert all(
        data["provenance"][key]
        for key in ("project_version", "sgp4_version", "astropy_version", "scipy_version")
    )
    assert data["configuration"]["analysis_start_utc"].endswith("Z")
    assert data["configuration"]["tle"]["epoch_utc"].endswith("Z")
    assert [item["station_name"] for item in data["station_access"]] == [
        station["name"] for station in FIXTURE["stations"]
    ]
    assert all(
        window["start_utc"].endswith("Z") and window["max_elevation_time_utc"].endswith("Z")
        for item in data["station_access"]
        for window in item["windows"]
    )
    assert data["coverage"]["analysis_end_utc"].endswith("Z")

    bundle = csv_bundle(first)
    assert tuple(bundle) == (
        "run.csv",
        "stations.csv",
        "access_windows.csv",
        "coverage.csv",
        "union_intervals.csv",
        "warnings.csv",
    )
    assert len(rows(bundle["run.csv"])) == 1
    assert rows(bundle["run.csv"])[0]["schema_version"] == "1.0"
    assert rows(bundle["run.csv"])[0]["tle_line1"] == FIXTURE["tle_line1"]
    assert len(rows(bundle["stations.csv"])) == 2
    assert [row["station_name"] for row in rows(bundle["access_windows.csv"])] == [
        station["name"] for station in FIXTURE["stations"]
    ]
    assert (
        float(rows(bundle["coverage.csv"])[0]["coverage_fraction"])
        == data["coverage"]["coverage_fraction"]
    )
    assert len(rows(bundle["union_intervals.csv"])) == len(data["coverage"]["union_intervals"])
    assert rows(bundle["warnings.csv"]) == []


def test_stale_tle_is_warning_not_failed_orbit() -> None:
    start = Time("2000-07-05T20:00:00", scale="utc")
    run_config = config(start=start, end=start + 10 * u.min, coarse_step_s=60)
    result = run_with_eop(run_config)
    assert result.status == RunStatus.SUCCESS_WITH_WARNINGS
    assert [notice.code for notice in result.notices] == ["TLE_AGE_WARNING"]
    details = dict(result.notices[0].details)
    assert details["max_abs_age_days"] > details["threshold_days"] == 7.0
    assert result.station_access is not None and result.coverage is not None
    assert rows(csv_bundle(result)["warnings.csv"])[0]["code"] == "TLE_AGE_WARNING"


def test_over_24_hour_span_is_evidence_warning_and_completes() -> None:
    start = Time(FIXTURE["analysis_start_utc"], scale="utc")
    run_config = config(start=start, end=start + 25 * u.hour, coarse_step_s=3600)
    result = run_with_eop(run_config)
    assert result.status == RunStatus.SUCCESS_WITH_WARNINGS
    assert [notice.code for notice in result.notices] == [
        "ANALYSIS_SPAN_OUTSIDE_VALIDATED_ENVELOPE"
    ]
    assert dict(result.notices[0].details) == {
        "analysis_span_hours": 25.0,
        "validated_max_hours": 24.0,
    }
    assert result.station_access is not None and result.coverage is not None


def assert_failed_result(result, code: str, stage: str) -> None:
    assert result.status == RunStatus.FAILED
    assert result.station_access is None
    assert result.coverage is None
    assert result.notices[-1].code == code
    assert result.notices[-1].severity == "ERROR"
    assert result.notices[-1].stage == stage
    data = result_dict(result)
    assert data["station_access"] is None and data["coverage"] is None
    bundle = csv_bundle(result)
    assert rows(bundle["run.csv"])[0]["status"] == "FAILED"
    assert rows(bundle["stations.csv"])
    assert rows(bundle["access_windows.csv"]) == []
    assert rows(bundle["coverage.csv"]) == []
    assert rows(bundle["union_intervals.csv"]) == []
    assert rows(bundle["warnings.csv"])[-1]["code"] == code


def test_missing_required_eop_fails_closed_without_cache_change(tmp_path: Path) -> None:
    # Real frame-service availability check, with a scoped table covering only 2001.
    unavailable = eop_table(Time("2001-01-01", scale="utc"), Time("2001-01-02", scale="utc"))
    with iers.conf.set_temp("auto_download", False), iers.earth_orientation_table.set(unavailable):
        run_config = config(earth_orientation_source="test-only unavailable 2001 EOP table")
        result = run_analysis(run_config)
        rerun = run_analysis(run_config)
    assert_failed_result(result, "EOP_UNAVAILABLE", "frame")
    assert serialize_json(result) == serialize_json(rerun)
    assert csv_bundle(result) == csv_bundle(rerun)
    assert "2000-06-27" in result.notices[-1].message
    assert write_json(result, tmp_path / "failed.json").exists()
    assert write_csv_bundle(result, tmp_path / "failed_csv")["warnings.csv"].exists()


def test_eop_table_acquisition_error_is_structured(monkeypatch) -> None:
    def unavailable():
        raise OSError("test-only EOP source unavailable")

    monkeypatch.setattr(frame_module.iers.earth_orientation_table, "get", unavailable)
    result = run_analysis(config(earth_orientation_source="test-only unavailable EOP source"))
    assert_failed_result(result, "EOP_UNAVAILABLE", "frame")


def test_sgp4_nonzero_error_fails_closed_through_real_adapter(monkeypatch) -> None:
    class FailedSatrec:
        def sgp4(self, jd1, jd2):
            return 6, (float("nan"),) * 3, (float("nan"),) * 3

    def error_propagator(tle):
        propagator = Sgp4Propagator(tle)
        propagator._satellite = FailedSatrec()
        return propagator

    monkeypatch.setattr(run_module, "Sgp4Propagator", error_propagator)
    first = run_with_eop(config())
    second = run_with_eop(config())
    assert_failed_result(first, "SGP4_PROPAGATION_ERROR", "propagation")
    assert dict(first.notices[-1].details)["sgp4_error_code"] == 6
    assert "SGP4 error 6" in first.notices[-1].message
    assert serialize_json(first) == serialize_json(second)
    assert csv_bundle(first) == csv_bundle(second)


def test_later_station_failure_discards_earlier_access(monkeypatch) -> None:
    class FailedSatrec:
        def sgp4(self, jd1, jd2):
            return 6, (float("nan"),) * 3, (float("nan"),) * 3

    original = run_module.find_satellite_access_windows
    calls = 0

    def fail_on_second_station(propagator, station, start, end, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            propagator._satellite = FailedSatrec()
        return original(propagator, station, start, end, **kwargs)

    monkeypatch.setattr(run_module, "find_satellite_access_windows", fail_on_second_station)
    result = run_with_eop(config())
    assert calls == 2
    assert_failed_result(result, "SGP4_PROPAGATION_ERROR", "propagation")


def test_successful_no_pass_is_not_failure() -> None:
    result = run_with_eop(config(minimum_elevation_deg=89.0))
    assert result.status == RunStatus.SUCCESS
    assert all(not item.windows for item in result.station_access)
    assert result.coverage.total_access_duration_s == 0
    assert result.coverage.coverage_fraction == 0
    assert result.coverage.access_window_count == 0
    assert result.coverage.longest_no_access_gap_s == pytest.approx(2400)
    assert all(notice.code != "SGP4_PROPAGATION_ERROR" for notice in result.notices)
    assert result_dict(result)["station_access"] != []
    assert rows(csv_bundle(result)["access_windows.csv"]) == []
    assert len(rows(csv_bundle(result)["coverage.csv"])) == 1


@pytest.mark.parametrize("end_offset_s", [0, -1])
def test_invalid_analysis_span_is_input_error(end_offset_s: int) -> None:
    start = Time(FIXTURE["analysis_start_utc"], scale="utc")
    with pytest.raises(ValueError, match="analysis end must be after start"):
        config(start=start, end=start + end_offset_s * u.s)


def test_naive_and_vector_time_are_input_errors() -> None:
    start = Time(FIXTURE["analysis_start_utc"], scale="utc")
    with pytest.raises(TypeError, match="scalar astropy.time.Time in UTC"):
        config(start=start.to_datetime())
    with pytest.raises(TypeError, match="scalar astropy.time.Time in UTC"):
        config(start=Time([FIXTURE["analysis_start_utc"]], scale="utc"))
