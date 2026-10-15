"""WGS84 station and station-to-satellite ENU geometry verification."""

from dataclasses import FrozenInstanceError
from datetime import datetime
from math import cos, isfinite, radians, sin

import astropy.units as u
import numpy as np
import pytest
from astropy.time import Time
from verification.wgs84 import A_M, B_M, geodetic_to_itrs_km

from spacecraft_mission_analysis import (
    EnuVector,
    GroundStation,
    ItrsPosition,
    ItrsState,
    RelativeItrsVector,
    itrs_to_enu,
    station_itrs_position,
    station_to_satellite_itrs,
)

# Fixed before evaluating production residuals: these check numerical agreement,
# not uncertainty in a surveyed station location or in the WGS84 realization.
WGS84_POSITION_TOLERANCE_KM = 1e-8
ENU_COMPONENT_TOLERANCE_KM = 1e-10
BASIS_TOLERANCE = 1e-14
TIME = Time("2020-01-01T12:00:00", scale="utc")


def _relative(station: GroundStation, vector_km: tuple[float, float, float]) -> RelativeItrsVector:
    return RelativeItrsVector(station, TIME.jd1, TIME.jd2, vector_km)


def _independent_basis(station: GroundStation) -> np.ndarray:
    latitude = radians(station.latitude_deg)
    longitude = radians(station.longitude_deg)
    sin_lat, cos_lat = sin(latitude), cos(latitude)
    sin_lon, cos_lon = sin(longitude), cos(longitude)
    return np.array(
        [
            [-sin_lon, cos_lon, 0.0],
            [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
            [cos_lat * cos_lon, cos_lat * sin_lon, sin_lat],
        ]
    )


@pytest.mark.parametrize(
    ("latitude_deg", "longitude_deg", "expected_km"),
    [
        (0.0, 0.0, (A_M / 1000.0, 0.0, 0.0)),
        (0.0, 90.0, (0.0, A_M / 1000.0, 0.0)),
        (90.0, 0.0, (0.0, 0.0, B_M / 1000.0)),
    ],
)
def test_wgs84_axis_cases(
    latitude_deg: float, longitude_deg: float, expected_km: tuple[float, float, float]
) -> None:
    station = GroundStation("axis", latitude_deg, longitude_deg, 0.0)
    position = station_itrs_position(station, TIME)
    residual_km = np.asarray(position.position_km) - expected_km
    assert isinstance(position, ItrsPosition)
    assert position.station is station
    assert position.time == TIME
    assert np.all(np.abs(residual_km) <= WGS84_POSITION_TOLERANCE_KM), residual_km


def test_arbitrary_wgs84_station_matches_independent_equations() -> None:
    station = GroundStation("arbitrary", 37.5, -122.25, 1234.5)
    position = station_itrs_position(station, TIME)
    reference = geodetic_to_itrs_km(station.latitude_deg, station.longitude_deg, station.height_m)
    residual_km = np.asarray(position.position_km) - reference
    assert np.all(np.abs(residual_km) <= WGS84_POSITION_TOLERANCE_KM), residual_km
    assert len(position.position_km) == 3
    assert all(isfinite(component) for component in position.position_km)
    returned_time = position.time
    returned_time.format = "mjd"
    assert position.time.format == "jd"
    with pytest.raises(FrozenInstanceError):
        position.position_km = (0.0, 0.0, 0.0)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        station.latitude_deg = 0.0  # type: ignore[misc]


def test_wgs84_longitude_boundary_near_pole_and_negative_height() -> None:
    east = station_itrs_position(GroundStation("east", 42.0, 180.0, -25.5), TIME)
    west = station_itrs_position(GroundStation("west", 42.0, -180.0, -25.5), TIME)
    near_pole_station = GroundStation("near pole", 89.99999, 120.0, 50.0)
    near_pole = station_itrs_position(near_pole_station, TIME)
    near_pole_reference = geodetic_to_itrs_km(89.99999, 120.0, 50.0)
    assert np.all(
        np.abs(np.asarray(east.position_km) - west.position_km) <= WGS84_POSITION_TOLERANCE_KM
    )
    assert np.all(
        np.abs(np.asarray(near_pole.position_km) - near_pole_reference)
        <= WGS84_POSITION_TOLERANCE_KM
    )
    assert np.all(
        np.abs(np.asarray(east.position_km) - geodetic_to_itrs_km(42.0, 180.0, -25.5))
        <= WGS84_POSITION_TOLERANCE_KM
    )


@pytest.mark.parametrize(
    ("latitude", "longitude", "height"),
    [
        (90.0001, 0.0, 0.0),
        (-90.0001, 0.0, 0.0),
        (0.0, 180.0001, 0.0),
        (0.0, -180.0001, 0.0),
        (float("nan"), 0.0, 0.0),
        (0.0, float("inf"), 0.0),
        (0.0, 0.0, float("-inf")),
    ],
)
def test_station_rejects_invalid_coordinates(
    latitude: float, longitude: float, height: float
) -> None:
    with pytest.raises(ValueError):
        GroundStation("invalid", latitude, longitude, height)


def test_station_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="name"):
        GroundStation(" ", 0.0, 0.0, 0.0)


@pytest.mark.parametrize(
    "bad_time",
    [
        datetime(2020, 1, 1, 12),
        "2020-01-01T12:00:00",
        Time("2020-01-01T12:00:00", scale="tai"),
        Time(["2020-01-01T12:00:00"], scale="utc"),
    ],
)
def test_station_position_requires_scalar_utc_time(bad_time: object) -> None:
    with pytest.raises(TypeError, match="scalar astropy.time.Time in UTC"):
        station_itrs_position(GroundStation("site", 0.0, 0.0, 0.0), bad_time)  # type: ignore[arg-type]


def test_station_relative_itrs_is_satellite_minus_station() -> None:
    station = GroundStation("site", 0.0, 0.0, 0.0)
    station_position = ItrsPosition(station, TIME.jd1, TIME.jd2, (6378.0, 20.0, -30.0))
    satellite = ItrsState(TIME.jd1, TIME.jd2, (6478.0, 22.0, -27.0), (0.0, 0.0, 0.0))
    relative = station_to_satellite_itrs(satellite, station_position)
    assert isinstance(relative, RelativeItrsVector)
    assert relative.station is station
    assert relative.time == TIME
    assert relative.vector_km == (100.0, 2.0, 3.0)


def test_station_position_relative_itrs_and_enu_compose() -> None:
    station = GroundStation("Greenwich equator", 0.0, 0.0, 0.0)
    station_position = station_itrs_position(station, TIME)
    x, y, z = station_position.position_km
    satellite = ItrsState(TIME.jd1, TIME.jd2, (x + 100.0, y, z), (0.0, 0.0, 0.0))
    enu = itrs_to_enu(station_to_satellite_itrs(satellite, station_position))
    residual_km = np.array([enu.east_km, enu.north_km, enu.up_km]) - [0.0, 0.0, 100.0]
    assert np.all(np.abs(residual_km) <= ENU_COMPONENT_TOLERANCE_KM), residual_km
    assert enu.station is station
    assert enu.time == TIME
    with pytest.raises(FrozenInstanceError):
        enu.up_km = 0.0  # type: ignore[misc]


def test_relative_itrs_rejects_wrong_frame_and_mismatched_epoch() -> None:
    station = GroundStation("site", 0.0, 0.0, 0.0)
    station_position = station_itrs_position(station, TIME)
    later = TIME + 1 * u.us
    later_satellite = ItrsState(later.jd1, later.jd2, (7000.0, 0.0, 0.0), (0.0,) * 3)
    with pytest.raises(ValueError, match="times must match exactly"):
        station_to_satellite_itrs(later_satellite, station_position)
    with pytest.raises(TypeError, match="ItrsState"):
        station_to_satellite_itrs(station_position, station_position)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="ItrsPosition"):
        station_to_satellite_itrs(later_satellite, later_satellite)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("itrs_km", "expected_enu_km"),
    [
        ((100.0, 0.0, 0.0), (0.0, 0.0, 100.0)),
        ((0.0, 100.0, 0.0), (100.0, 0.0, 0.0)),
        ((0.0, 0.0, 100.0), (0.0, 100.0, 0.0)),
    ],
)
def test_equator_greenwich_enu_axes(
    itrs_km: tuple[float, float, float], expected_enu_km: tuple[float, float, float]
) -> None:
    station = GroundStation("Greenwich equator", 0.0, 0.0, 0.0)
    enu = itrs_to_enu(_relative(station, itrs_km))
    actual = np.array([enu.east_km, enu.north_km, enu.up_km])
    assert isinstance(enu, EnuVector)
    assert enu.station is station
    assert enu.time == TIME
    assert np.all(np.abs(actual - expected_enu_km) <= ENU_COMPONENT_TOLERANCE_KM)


def test_arbitrary_enu_reconstruction_and_basis_invariants() -> None:
    station = GroundStation("oblique", 45.0, 30.0, 100.0)
    independent_basis = _independent_basis(station)
    rho_km = independent_basis.T @ np.array([100.0, 200.0, 300.0])
    enu = itrs_to_enu(_relative(station, tuple(rho_km)))
    residual_km = np.array([enu.east_km, enu.north_km, enu.up_km]) - [100.0, 200.0, 300.0]
    assert np.all(np.abs(residual_km) <= ENU_COMPONENT_TOLERANCE_KM), residual_km

    for latitude, longitude in ((0.0, 0.0), (45.0, 30.0), (-33.8, -151.2), (89.99999, 120.0)):
        station = GroundStation("basis", latitude, longitude, 0.0)
        columns = []
        for unit_itrs in np.eye(3):
            projected = itrs_to_enu(_relative(station, tuple(unit_itrs)))
            columns.append((projected.east_km, projected.north_km, projected.up_km))
        production_basis = np.array(columns).T
        assert np.all(np.abs(production_basis - _independent_basis(station)) <= BASIS_TOLERANCE)
        assert np.all(np.abs(production_basis @ production_basis.T - np.eye(3)) <= BASIS_TOLERANCE)
        assert np.all(
            np.abs(np.cross(production_basis[0], production_basis[1]) - production_basis[2])
            <= BASIS_TOLERANCE
        )


def test_longitude_boundary_enu_equivalence_and_pole_convention() -> None:
    vector_km = (17.0, -23.0, 41.0)
    plus_180 = itrs_to_enu(_relative(GroundStation("east", 20.0, 180.0, 0.0), vector_km))
    minus_180 = itrs_to_enu(_relative(GroundStation("west", 20.0, -180.0, 0.0), vector_km))
    assert np.all(
        np.abs(
            np.array([plus_180.east_km, plus_180.north_km, plus_180.up_km])
            - [minus_180.east_km, minus_180.north_km, minus_180.up_km]
        )
        <= ENU_COMPONENT_TOLERANCE_KM
    )
    # At the exact pole, longitude selects a local East/North orientation.
    pole_zero = itrs_to_enu(_relative(GroundStation("pole 0", 90.0, 0.0, 0.0), vector_km))
    pole_east = itrs_to_enu(_relative(GroundStation("pole 90", 90.0, 90.0, 0.0), vector_km))
    assert pole_zero.east_km != pole_east.east_km


def test_geodetic_up_differs_from_geocentric_radial_direction() -> None:
    station = GroundStation("midlatitude", 45.0, 30.0, 0.0)
    position = station_itrs_position(station, TIME)
    radial = np.asarray(position.position_km) / np.linalg.norm(position.position_km)
    geodetic_up = _independent_basis(station)[2]
    assert np.linalg.norm(geodetic_up - radial) > 0.0
    projected = itrs_to_enu(_relative(station, tuple(radial)))
    expected_north = _independent_basis(station)[1] @ radial
    assert abs(projected.north_km - expected_north) <= ENU_COMPONENT_TOLERANCE_KM
    assert projected.north_km != 0.0


def test_enu_rejects_unlabelled_vector() -> None:
    with pytest.raises(TypeError, match="RelativeItrsVector"):
        itrs_to_enu((1.0, 2.0, 3.0))  # type: ignore[arg-type]
