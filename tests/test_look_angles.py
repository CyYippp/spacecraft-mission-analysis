"""Analytic ENU-to-azimuth/elevation/range boundary cases."""

from dataclasses import FrozenInstanceError
from math import asin, degrees, sqrt

import pytest
from astropy.time import Time

from spacecraft_mission_analysis import (
    AzElRange,
    EnuVector,
    GroundStation,
    ItrsState,
    enu_to_az_el_range,
    itrs_to_enu,
    station_itrs_position,
    station_to_satellite_itrs,
)

# Fixed before evaluating the implementation: software arithmetic agreement,
# not angular or range uncertainty from orbit and station inputs.
ANGLE_TOLERANCE_DEG = 1e-12
RANGE_TOLERANCE_KM = 1e-12
TIME = Time("2020-01-01T12:00:00", scale="utc")
STATION = GroundStation("reference", 45.0, 30.0, 100.0)


def _enu(east_km: float, north_km: float, up_km: float) -> EnuVector:
    return EnuVector(STATION, TIME.jd1, TIME.jd2, east_km, north_km, up_km)


@pytest.mark.parametrize(
    ("east_km", "north_km", "expected_azimuth_deg"),
    [
        (0.0, 100.0, 0.0),
        (100.0, 0.0, 90.0),
        (0.0, -100.0, 180.0),
        (-100.0, 0.0, 270.0),
    ],
)
def test_cardinal_directions_on_horizon(
    east_km: float, north_km: float, expected_azimuth_deg: float
) -> None:
    result = enu_to_az_el_range(_enu(east_km, north_km, 0.0))
    assert isinstance(result, AzElRange)
    assert result.azimuth_deg is not None
    assert abs(result.azimuth_deg - expected_azimuth_deg) <= ANGLE_TOLERANCE_DEG
    assert abs(result.elevation_deg) <= ANGLE_TOLERANCE_DEG
    assert abs(result.range_km - 100.0) <= RANGE_TOLERANCE_KM


@pytest.mark.parametrize(
    ("east_km", "north_km", "expected_azimuth_deg"),
    [
        (100.0, 100.0, 45.0),
        (100.0, -100.0, 135.0),
        (-100.0, -100.0, 225.0),
        (-100.0, 100.0, 315.0),
    ],
)
def test_azimuth_quadrants(east_km: float, north_km: float, expected_azimuth_deg: float) -> None:
    result = enu_to_az_el_range(_enu(east_km, north_km, 0.0))
    assert result.azimuth_deg is not None
    assert abs(result.azimuth_deg - expected_azimuth_deg) <= ANGLE_TOLERANCE_DEG
    assert abs(result.elevation_deg) <= ANGLE_TOLERANCE_DEG
    assert abs(result.range_km - sqrt(20000.0)) <= RANGE_TOLERANCE_KM


@pytest.mark.parametrize(("up_km", "expected_elevation_deg"), [(100.0, 90.0), (-100.0, -90.0)])
def test_zenith_and_nadir_have_undefined_azimuth(
    up_km: float, expected_elevation_deg: float
) -> None:
    result = enu_to_az_el_range(_enu(0.0, 0.0, up_km))
    assert result.azimuth_deg is None
    assert abs(result.elevation_deg - expected_elevation_deg) <= ANGLE_TOLERANCE_DEG
    assert abs(result.range_km - 100.0) <= RANGE_TOLERANCE_KM


def test_exact_horizon_and_independent_range_norm() -> None:
    horizon = enu_to_az_el_range(_enu(3.0, 4.0, 0.0))
    assert horizon.azimuth_deg is not None
    assert abs(horizon.azimuth_deg - degrees(asin(3.0 / 5.0))) <= ANGLE_TOLERANCE_DEG
    assert abs(horizon.elevation_deg) <= ANGLE_TOLERANCE_DEG
    assert abs(horizon.range_km - 5.0) <= RANGE_TOLERANCE_KM

    oblique = enu_to_az_el_range(_enu(3.0, 4.0, 12.0))
    assert oblique.azimuth_deg is not None
    assert abs(oblique.azimuth_deg - degrees(asin(3.0 / 5.0))) <= ANGLE_TOLERANCE_DEG
    assert abs(oblique.elevation_deg - degrees(asin(12.0 / 13.0))) <= ANGLE_TOLERANCE_DEG
    assert abs(oblique.range_km - sqrt(3.0**2 + 4.0**2 + 12.0**2)) <= RANGE_TOLERANCE_KM


def test_station_to_look_angles_chain_with_synthetic_itrs_satellite() -> None:
    station = GroundStation("Greenwich equator", 0.0, 0.0, 0.0)
    station_position = station_itrs_position(station, TIME)
    x, y, z = station_position.position_km
    satellite = ItrsState(TIME.jd1, TIME.jd2, (x + 100.0, y + 100.0, z), (0.0,) * 3)
    enu = itrs_to_enu(station_to_satellite_itrs(satellite, station_position))
    result = enu_to_az_el_range(enu)
    assert result.azimuth_deg is not None
    assert abs(result.azimuth_deg - 90.0) <= ANGLE_TOLERANCE_DEG
    assert abs(result.elevation_deg - 45.0) <= ANGLE_TOLERANCE_DEG
    assert abs(result.range_km - sqrt(20000.0)) <= RANGE_TOLERANCE_KM
    assert result.station is station
    assert result.time == TIME


def test_no_hidden_near_zenith_threshold() -> None:
    result = enu_to_az_el_range(_enu(1e-9, 0.0, 100.0))
    assert result.azimuth_deg is not None
    assert abs(result.azimuth_deg - 90.0) <= ANGLE_TOLERANCE_DEG


def test_result_retains_station_time_and_is_immutable() -> None:
    result = enu_to_az_el_range(_enu(3.0, 4.0, 12.0))
    assert result.station is STATION
    assert result.time == TIME
    returned_time = result.time
    returned_time.format = "mjd"
    assert result.time.format == "jd"
    with pytest.raises(FrozenInstanceError):
        result.range_km = 0.0  # type: ignore[misc]


@pytest.mark.parametrize(
    ("east_km", "north_km", "up_km"),
    [
        (0.0, 0.0, 0.0),
        (float("nan"), 0.0, 1.0),
        (0.0, float("inf"), 1.0),
        (0.0, 1.0, float("-inf")),
        (1.2e308, 1.2e308, 1.2e308),
    ],
)
def test_zero_or_nonfinite_displacement_is_explicit_failure(
    east_km: float, north_km: float, up_km: float
) -> None:
    with pytest.raises(ValueError):
        enu_to_az_el_range(_enu(east_km, north_km, up_km))


def test_unlabelled_vector_is_rejected() -> None:
    with pytest.raises(TypeError, match="EnuVector"):
        enu_to_az_el_range((1.0, 2.0, 3.0))  # type: ignore[arg-type]
