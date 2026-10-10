"""Independent published TEME/ITRF state and Earth-orientation failure checks."""

import json
from contextlib import contextmanager
from math import isfinite
from pathlib import Path

import astropy.units as u
import pytest
from astropy.time import Time
from astropy.utils import iers

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


def _reference_residuals() -> tuple[list[float], list[float]]:
    with _published_eop():
        actual = teme_to_itrs(_reference_state())

    position_residual_km = [
        got - expected
        for got, expected in zip(
            actual.position_km, FIXTURE["published_itrf_position_km"], strict=True
        )
    ]
    velocity_residual_km_s = [
        got - expected
        for got, expected in zip(
            actual.velocity_km_s, FIXTURE["published_itrf_velocity_km_s"], strict=True
        )
    ]
    return position_residual_km, velocity_residual_km_s


@pytest.mark.xfail(
    strict=True,
    reason="Vallado x-position residual is 13.17 mm against the predeclared 10 mm limit",
)
def test_vallado_appendix_c_position() -> None:
    # This known discrepancy remains visible; do not relax the frozen limit.
    position_residual_km, _ = _reference_residuals()
    assert all(abs(value) <= POSITION_TOLERANCE_KM for value in position_residual_km), (
        f"Vallado position residuals (km): {position_residual_km}"
    )


def test_vallado_appendix_c_velocity() -> None:
    # Missing Earth-rotation velocity gives errors far above this limit.
    _, velocity_residual_km_s = _reference_residuals()
    assert all(abs(value) <= VELOCITY_TOLERANCE_KM_S for value in velocity_residual_km_s), (
        f"Vallado velocity residuals (km/s): {velocity_residual_km_s}"
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
