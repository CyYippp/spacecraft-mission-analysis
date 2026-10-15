"""Archived-orbit access smoke case with test-only deterministic EOP inputs."""

import json
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
            assert abs(satellite_elevation_deg(propagator, station, window.start) - 10) <= (
                MASK_RESIDUAL_LIMIT_DEG
            )
            assert abs(satellite_elevation_deg(propagator, station, window.end) - 10) <= (
                MASK_RESIDUAL_LIMIT_DEG
            )


def test_propagation_failure_cannot_become_no_access() -> None:
    propagator, station, start, end = _setup()

    class FailedSatrec:
        def sgp4(self, jd1, jd2):
            return 6, (float("nan"),) * 3, (float("nan"),) * 3

    propagator._satellite = FailedSatrec()
    with pytest.raises(PropagationError, match="SGP4 error 6"):
        find_satellite_access_windows(propagator, station, start, end)
