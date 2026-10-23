"""Independent published TEME/ITRF state and Earth-orientation failure checks."""

import json
from contextlib import contextmanager
from math import isfinite
from pathlib import Path

import astropy.units as u
import erfa
import numpy as np
import pytest
from astropy.time import Time
from astropy.utils import iers
from verification.vallado import gmst1982, teme_to_itrf_vallado

from spacecraft_mission_analysis import FrameTransformError, ItrsState, TemeState, teme_to_itrs

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "frames" / "vallado_appendix_c.json").read_text(
        encoding="utf-8"
    )
)
POSITION_TOLERANCE_KM = 1e-5
VELOCITY_TOLERANCE_KM_S = 1e-7


def _reference_state() -> TemeState:
    time = Time(FIXTURE["time_utc"], scale="utc")
    return TemeState(
        time.jd1,
        time.jd2,
        tuple(FIXTURE["teme_position_km"]),
        tuple(FIXTURE["teme_velocity_km_s"]),
        0.0,  # Synthetic published vector; no source TLE offset is asserted.
    )


@contextmanager
def _published_eop():
    """Supply the paper's EOP at its epoch, without changing process-wide defaults."""
    with iers.conf.set_temp("auto_download", False):
        day = int(_reference_state().time.mjd)
        table = iers.IERS(
            {
                "MJD": [day, day + 1] * u.day,
                "UT1_UTC": [FIXTURE["ut1_minus_utc_s"]] * 2 * u.s,
                "PM_x": [FIXTURE["xp_arcsec"]] * 2 * u.arcsec,
                "PM_y": [FIXTURE["yp_arcsec"]] * 2 * u.arcsec,
            }
        )
        with iers.earth_orientation_table.set(table):
            yield


def _matched_split_residuals() -> tuple[np.ndarray, np.ndarray]:
    with _published_eop():
        state = _reference_state()
        ut1 = state.time.ut1
        expected_position, expected_velocity = teme_to_itrf_vallado(
            ut1.jd1,
            ut1.jd2,
            FIXTURE["teme_position_km"],
            FIXTURE["teme_velocity_km_s"],
            FIXTURE["xp_arcsec"],
            FIXTURE["yp_arcsec"],
        )
        actual = teme_to_itrs(state)
        assert abs(gmst1982(ut1.jd1, ut1.jd2)[0] - erfa.gmst82(ut1.jd1, ut1.jd2)) < 1e-12
    return (
        np.asarray(actual.position_km) - expected_position,
        np.asarray(actual.velocity_km_s) - expected_velocity,
    )


def test_published_appendix_c_single_jd_reference_reproduction() -> None:
    """Reproduce the printed vector through Skyfield's historical single-JD path.

    Source: skyfielders/python-skyfield at commit 31a6ed7584cd09b6e48e07546a4b5921e1cd5bb4,
    skyfield/tests/test_earth_satellites.py, skyfield/sgp4lib.py, and skyfield/timelib.py.
    The 5e-8 km and 7e-8 km/s limits below are Skyfield's own test criteria,
    not replacements for this project's frozen position/velocity criteria.
    """
    # Match the evaluation order in Skyfield's published Appendix C test.
    assert FIXTURE["time_utc"] == "2004-04-06T07:51:28.386"
    jd_utc_single = 2453101.5 + (7 * 3600 + 51 * 60 + 28.386) / 86400.0
    jd_ut1_single = jd_utc_single + FIXTURE["ut1_minus_utc_s"] / 86400.0
    single_position, single_velocity = teme_to_itrf_vallado(
        jd_ut1_single,
        0.0,
        FIXTURE["teme_position_km"],
        FIXTURE["teme_velocity_km_s"],
        FIXTURE["xp_arcsec"],
        FIXTURE["yp_arcsec"],
    )

    assert np.allclose(single_position, FIXTURE["published_itrf_position_km"], rtol=0, atol=5e-8)
    assert np.allclose(single_velocity, FIXTURE["published_itrf_velocity_km_s"], rtol=0, atol=7e-8)


def test_production_matches_independent_split_ut1_position() -> None:
    position_residual_km, _ = _matched_split_residuals()
    assert np.all(np.abs(position_residual_km) <= POSITION_TOLERANCE_KM), (
        f"Matched split-UT1 position residuals (km): {position_residual_km}"
    )


def test_production_matches_independent_split_ut1_velocity() -> None:
    # Missing Earth-rotation velocity gives errors far above this limit.
    _, velocity_residual_km_s = _matched_split_residuals()
    assert np.all(np.abs(velocity_residual_km_s) <= VELOCITY_TOLERANCE_KM_S), (
        f"Matched split-UT1 velocity residuals (km/s): {velocity_residual_km_s}"
    )


def test_itrs_state_contract_and_scoped_earth_orientation() -> None:
    original_download = iers.conf.auto_download
    with iers.conf.set_temp("auto_download", False):
        original_table = iers.earth_orientation_table.get()
        with _published_eop():
            actual = teme_to_itrs(_reference_state())
            assert isinstance(actual, ItrsState)
            assert actual.time.scale == "utc"
            assert actual.time == _reference_state().time
            assert (actual._time_jd1, actual._time_jd2) == (
                _reference_state()._time_jd1,
                _reference_state()._time_jd2,
            )
            assert len(actual.position_km) == len(actual.velocity_km_s) == 3
            assert all(isfinite(value) for value in (*actual.position_km, *actual.velocity_km_s))
        assert iers.earth_orientation_table.get() is original_table
    assert iers.conf.auto_download == original_download


def test_out_of_range_earth_orientation_raises_before_a_state_is_returned() -> None:
    table = iers.IERS(
        {
            "MJD": [53000, 53001] * u.day,
            "UT1_UTC": [0.0, 0.0] * u.s,
            "PM_x": [0.0, 0.0] * u.arcsec,
            "PM_y": [0.0, 0.0] * u.arcsec,
        }
    )
    with iers.conf.set_temp("auto_download", False), iers.earth_orientation_table.set(table):
        with pytest.raises(FrameTransformError, match="Earth-orientation data unavailable"):
            teme_to_itrs(_reference_state())


def test_frame_transform_requires_teme_state() -> None:
    with pytest.raises(TypeError, match="TemeState"):
        teme_to_itrs(Time(FIXTURE["time_utc"], scale="utc"))
