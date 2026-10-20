"""Archived-orbit access smoke case with test-only deterministic EOP inputs."""

import json
from math import isfinite
from pathlib import Path

import astropy.units as u
import pytest
from astropy.time import Time
from astropy.utils import iers

from spacecraft_mission_analysis import (
    GroundStation,
    PropagationError,
    Sgp4Propagator,
    TleRecord,
    compute_temporal_coverage,
    find_satellite_access_windows,
    satellite_elevation_deg,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "access" / "vanguard_greenwich.json").read_text(
        encoding="utf-8"
    )
)
# Refined crossing at 0.01 s gives a much smaller mask residual for this pass;
# 0.01 deg is a predeclared numerical integration check, not physical accuracy.
MASK_RESIDUAL_LIMIT_DEG = 0.01
PEAK_NEIGHBOR_SLACK_DEG = 1e-8  # Numerical comparison, not angular accuracy.


def _setup():
    tle = TleRecord.from_lines(
        FIXTURE["tle_line1"], FIXTURE["tle_line2"], source=FIXTURE["tle_provenance"]
    )
    return (
        Sgp4Propagator(tle),
        GroundStation(**FIXTURE["station"]),
        Time(FIXTURE["analysis_start_utc"], scale="utc"),
        Time(FIXTURE["analysis_end_utc"], scale="utc"),
    )


def _eop_table():
    values = FIXTURE["test_only_eop"]
    return iers.IERS(
        {
            "MJD": values["mjd"] * u.day,
            "UT1_UTC": values["ut1_minus_utc_s"] * u.s,
            "PM_x": values["xp_arcsec"] * u.arcsec,
            "PM_y": values["yp_arcsec"] * u.arcsec,
        }
    )


def test_archived_tle_to_access_smoke() -> None:
    propagator, station, start, end = _setup()
    with iers.conf.set_temp("auto_download", False), iers.earth_orientation_table.set(_eop_table()):
        windows = find_satellite_access_windows(
            propagator,
            station,
            start,
            end,
            coarse_step_s=FIXTURE["coarse_step_s"],
            root_tolerance_s=FIXTURE["root_tolerance_s"],
        )
        assert len(windows) == FIXTURE["expected_window_count"]
        for window in windows:
            assert start < window.start < window.end < end
            assert not window.start_clipped and not window.end_clipped
            assert window.duration_s > 0
            assert window.max_elevation_time.scale == "utc"
            assert window.start <= window.max_elevation_time <= window.end
            assert isfinite(window.max_elevation_deg)
            assert abs(satellite_elevation_deg(propagator, station, window.start) - 10) <= (
                MASK_RESIDUAL_LIMIT_DEG
            )
            assert abs(satellite_elevation_deg(propagator, station, window.end) - 10) <= (
                MASK_RESIDUAL_LIMIT_DEG
            )
            peak = satellite_elevation_deg(propagator, station, window.max_elevation_time)
            assert abs(peak - window.max_elevation_deg) <= 1e-10
            for offset_s in (-5.0, -1.0, 1.0, 5.0):
                nearby = window.max_elevation_time + offset_s * u.s
                if window.start <= nearby <= window.end:
                    assert peak >= satellite_elevation_deg(propagator, station, nearby) - (
                        PEAK_NEIGHBOR_SLACK_DEG
                    )


def test_propagation_failure_cannot_become_no_access() -> None:
    propagator, station, start, end = _setup()

    class FailedSatrec:
        def sgp4(self, jd1, jd2):
            return 6, (float("nan"),) * 3, (float("nan"),) * 3

    propagator._satellite = FailedSatrec()
    with pytest.raises(PropagationError, match="SGP4 error 6"):
        find_satellite_access_windows(propagator, station, start, end)


def test_two_station_temporal_coverage_integration() -> None:
    """Archived-orbit wiring check; analytic tests establish metric correctness."""
    propagator, greenwich, start, end = _setup()
    second = GroundStation(
        name="Synthetic 1N 1E WGS84 station",
        latitude_deg=1.0,
        longitude_deg=1.0,
        height_m=0.0,
    )
    with iers.conf.set_temp("auto_download", False), iers.earth_orientation_table.set(_eop_table()):
        by_station = {
            greenwich.name: find_satellite_access_windows(propagator, greenwich, start, end),
            second.name: find_satellite_access_windows(propagator, second, start, end),
        }
    windows = tuple(window for station_windows in by_station.values() for window in station_windows)
    result = compute_temporal_coverage(start, end, windows)
    assert by_station[greenwich.name] and by_station[second.name]
    assert all(start <= item.start < item.end <= end for item in result.union_intervals)
    assert 0 < result.total_access_duration_s <= (end - start).to_value(u.s)
    assert 0 < result.coverage_fraction <= 1
    assert result.access_window_count == len(result.union_intervals)
    # The two real solver windows overlap; their raw sum must double-count time.
    assert sum(window.duration_s for window in windows) > result.total_access_duration_s
    assert result.longest_no_access_gap_s >= 0
    print(
        "\nMA-08 archived integration:",
        {
            name: [(w.start.isot, w.end.isot, w.duration_s) for w in items]
            for name, items in by_station.items()
        },
        "union:",
        [(item.start.isot, item.end.isot, item.duration_s) for item in result.union_intervals],
        "metrics:",
        (
            result.total_access_duration_s,
            result.coverage_fraction,
            result.access_window_count,
            result.longest_no_access_gap_s,
            None
            if result.longest_no_access_gap is None
            else (
                result.longest_no_access_gap.start.isot,
                result.longest_no_access_gap.end.isot,
            ),
        ),
    )
