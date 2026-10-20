"""Archived TLE and versioned input boundary; no live ephemeris or IERS data."""

import copy
import csv
import io
import json
from pathlib import Path

import astropy.units as u
import pytest
from astropy.time import Time
from astropy.utils import iers
from sgp4.io import fix_checksum

from spacecraft_mission_analysis import (
    InputConfigError,
    RunStatus,
    TleRecord,
    csv_bundle,
    load_analysis_config,
    parse_analysis_config,
    result_dict,
    run_analysis,
)

EXAMPLE = Path(__file__).parent.parent / "examples" / "vanguard_run"
BASE = json.loads((EXAMPLE / "config.json").read_text(encoding="utf-8"))
EOP = json.loads((EXAMPLE / "test_only_eop.json").read_text(encoding="utf-8"))


def changed(**updates: object) -> dict:
    data = copy.deepcopy(BASE)
    data.update(updates)
    return data


def test_archived_vanguard_input_preserves_raw_tle_epoch_source_and_settings() -> None:
    config = load_analysis_config(EXAMPLE / "config.json")
    assert (
        config.tle.line1 == "1 00005U 58002B   00179.78495062  .00000023  00000-0  28098-4 0  4753"
    )
    assert (
        config.tle.line2 == "2 00005  34.2682 348.7242 1859667 331.7664  19.3264 10.82419157413667"
    )
    assert config.tle.catalog_id == 5
    assert (
        config.tle.source
        == "Vallado / python-sgp4 2.27 verification case 00005; tests/fixtures/sgp4/README.md"
    )
    epoch = config.tle.epoch
    epoch.precision = 9
    assert epoch.scale == "utc"
    assert epoch.isot == "2000-06-27T18:50:19.733568000"
    assert [station.name for station in config.stations] == [
        "Equator Greenwich synthetic fixed WGS84 station",
        "Synthetic 1N 1E WGS84 station",
    ]
    assert [
        (station.latitude_deg, station.longitude_deg, station.height_m)
        for station in config.stations
    ] == [
        (0.0, 0.0, 0.0),
        (1.0, 1.0, 0.0),
    ]
    assert config.start.isot == "2000-06-27T20:00:00.000"
    assert config.end.isot == "2000-06-27T20:40:00.000"
    assert (config.minimum_elevation_deg, config.coarse_step_s, config.root_tolerance_s) == (
        10.0,
        5.0,
        0.01,
    )
    assert (
        config.earth_orientation_source
        == "test-only synthetic zero UT1-UTC/xp/yp IERS table at MJD 51722-51723"
    )


@pytest.mark.parametrize(
    ("fault", "line1", "line2", "message"),
    [
        ("line 1 prefix", "0" + BASE["tle_line1"][1:], BASE["tle_line2"], "line 1"),
        ("line 2 prefix", BASE["tle_line1"], "0" + BASE["tle_line2"][1:], "line 2"),
        ("line 1 checksum digit", BASE["tle_line1"][:-1] + "4", BASE["tle_line2"], "checksum"),
        ("line 2 checksum digit", BASE["tle_line1"], BASE["tle_line2"][:-1] + "8", "checksum"),
        ("line 2 checksum character", BASE["tle_line1"], BASE["tle_line2"][:-1] + "X", "checksum"),
        (
            "catalogue mismatch",
            BASE["tle_line1"],
            fix_checksum("2 00006" + BASE["tle_line2"][7:]),
            "catalogue identifiers",
        ),
        (
            "unparseable epoch",
            fix_checksum(BASE["tle_line1"][:18] + "XX" + BASE["tle_line1"][20:]),
            BASE["tle_line2"],
            "parsed by SGP4",
        ),
        ("truncated required line", BASE["tle_line1"], BASE["tle_line2"][:-10], "line 2"),
        (
            "malformed mean element",
            BASE["tle_line1"],
            fix_checksum(BASE["tle_line2"][:8] + "x" + BASE["tle_line2"][9:]),
            "parsed by SGP4",
        ),
        (
            "zero mean motion",
            BASE["tle_line1"],
            fix_checksum(BASE["tle_line2"][:52] + " 0.00000000" + BASE["tle_line2"][63:]),
            "parsed by SGP4",
        ),
    ],
)
def test_invalid_tle_rejected(fault: str, line1: str, line2: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        TleRecord.from_lines(line1, line2, source=BASE["tle_source"])
    with pytest.raises(InputConfigError, match=message):
        parse_analysis_config(changed(tle_line1=line1, tle_line2=line2))


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"schema_version": "2.0"}, "schema_version"),
        ({"tle_source": ""}, "tle_source"),
        ({"tle_source": 42}, "tle_source"),
        ({"minimum_elevaton_deg": 5}, "unknown field"),
        ({"minimum_elevation_deg": "10"}, "minimum_elevation_deg"),
        ({"coarse_step_s": True}, "coarse_step_s"),
        ({"analysis_start_utc": "2000-06-27T20:00:00"}, "analysis_start_utc"),
        ({"analysis_start_utc": "2000-06-27T21:00:00+01:00"}, "analysis_start_utc"),
        ({"analysis_start_utc": ["2000-06-27T20:00:00Z"]}, "analysis_start_utc"),
        ({"analysis_start_utc": "2000-13-27T20:00:00Z"}, "analysis_start_utc"),
        ({"analysis_end_utc": "2000-06-27T20:00:00Z"}, "after start"),
        ({"analysis_end_utc": "2000-06-27T19:59:59Z"}, "after start"),
        ({"stations": []}, "stations"),
    ],
)
def test_invalid_input_rejected(updates: dict, message: str) -> None:
    with pytest.raises(InputConfigError, match=message):
        parse_analysis_config(changed(**updates))


@pytest.mark.parametrize(
    "key", ["schema_version", "tle_line1", "tle_line2", "tle_source", "stations"]
)
def test_required_field_missing(key: str) -> None:
    data = changed()
    del data[key]
    with pytest.raises(InputConfigError, match=key):
        parse_analysis_config(data)


@pytest.mark.parametrize(
    ("station", "message"),
    [
        ({"latitude_deg": 0.0, "longitude_deg": 0.0, "height_m": 0.0}, "name"),
        (
            {"name": "x", "latitude_deg": 91.0, "longitude_deg": 0.0, "height_m": 0.0},
            "latitude_deg",
        ),
        (
            {"name": "x", "latitude_deg": 0.0, "longitude_deg": 181.0, "height_m": 0.0},
            "longitude_deg",
        ),
        ({"name": "x", "latitude_deg": 0.0, "longitude_deg": 0.0, "height_m": "0"}, "height_m"),
        (
            {
                "name": "x",
                "latitude_deg": 0.0,
                "longitude_deg": 0.0,
                "height_m": 0.0,
                "altitude_m": 0.0,
            },
            "unknown field",
        ),
    ],
)
def test_station_contract_uses_groundstation_validation(station: dict, message: str) -> None:
    with pytest.raises(InputConfigError, match=message):
        parse_analysis_config(changed(stations=[station]))


def test_optional_defaults_and_explicit_settings() -> None:
    data = changed()
    for key in ("minimum_elevation_deg", "coarse_step_s", "root_tolerance_s"):
        del data[key]
    default = parse_analysis_config(data)
    assert (default.minimum_elevation_deg, default.coarse_step_s, default.root_tolerance_s) == (
        10.0,
        5.0,
        0.01,
    )
    assert default.source_revision is None
    explicit = parse_analysis_config(
        changed(
            minimum_elevation_deg=7.5,
            coarse_step_s=2,
            root_tolerance_s=0.005,
            source_revision="archived-build",
        )
    )
    assert (
        explicit.minimum_elevation_deg,
        explicit.coarse_step_s,
        explicit.root_tolerance_s,
        explicit.source_revision,
    ) == (7.5, 2.0, 0.005, "archived-build")


def test_json_duplicate_field_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.json"
    path.write_text('{"schema_version":"1.0","schema_version":"1.0"}', encoding="utf-8")
    with pytest.raises(InputConfigError, match="duplicate JSON field"):
        load_analysis_config(path)


def test_archived_config_to_run_and_output_matches_saved_result() -> None:
    config = load_analysis_config(EXAMPLE / "config.json")
    table = iers.IERS(
        {
            "MJD": EOP["mjd"] * u.day,
            "UT1_UTC": EOP["ut1_minus_utc_s"] * u.s,
            "PM_x": EOP["xp_arcsec"] * u.arcsec,
            "PM_y": EOP["yp_arcsec"] * u.arcsec,
        }
    )
    with iers.conf.set_temp("auto_download", False), iers.earth_orientation_table.set(table):
        result = run_analysis(config)
    assert result.status == RunStatus.SUCCESS
    actual = result_dict(result)
    saved = json.loads((EXAMPLE / "run.json").read_text(encoding="utf-8"))
    assert actual["configuration"] == saved["configuration"]
    assert actual["provenance"] == saved["provenance"]
    assert actual["coverage"] == saved["coverage"]
    assert actual["notices"] == saved["notices"] == []
    for current_station, saved_station in zip(actual["station_access"], saved["station_access"]):
        assert current_station["station_name"] == saved_station["station_name"]
        assert len(current_station["windows"]) == len(saved_station["windows"]) == 1
        current, reference = current_station["windows"][0], saved_station["windows"][0]
        assert abs(current["max_elevation_deg"] - reference["max_elevation_deg"]) <= 1e-5
        assert (
            abs(
                (
                    Time(current["max_elevation_time_utc"][:-1], scale="utc")
                    - Time(reference["max_elevation_time_utc"][:-1], scale="utc")
                ).to_value(u.s)
            )
            <= 0.02
        )
        current = {
            key: value
            for key, value in current.items()
            if key not in ("max_elevation_deg", "max_elevation_time_utc")
        }
        reference = {
            key: value
            for key, value in reference.items()
            if key not in ("max_elevation_deg", "max_elevation_time_utc")
        }
        assert current == reference
    bundle = csv_bundle(result)
    for name, content in bundle.items():
        if name != "access_windows.csv":
            assert content.encode("utf-8") == (EXAMPLE / "csv" / name).read_bytes()
            continue
        saved_csv = (EXAMPLE / "csv" / name).read_text(encoding="utf-8")
        assert content.splitlines(keepends=True)[0] == saved_csv.splitlines(keepends=True)[0]
        actual_rows = list(csv.DictReader(io.StringIO(content)))
        saved_rows = list(csv.DictReader(io.StringIO(saved_csv)))
        assert len(actual_rows) == len(saved_rows) == 2
        for current, reference in zip(actual_rows, saved_rows):
            current["max_elevation_deg"] = reference["max_elevation_deg"]
            current["max_elevation_time_utc"] = reference["max_elevation_time_utc"]
            assert current == reference
    assert config.tle.line1 == actual["configuration"]["tle"]["line1"]
    assert config.tle.line2 == actual["configuration"]["tle"]["line2"]
    assert config.tle.source == actual["configuration"]["tle"]["source"]
