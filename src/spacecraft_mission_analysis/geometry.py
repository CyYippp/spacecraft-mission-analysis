"""Station-relative ITRS displacement and local geodetic ENU projection."""

from dataclasses import dataclass
from math import cos, radians, sin

from astropy.time import Time

from .frames import ItrsState
from .stations import GroundStation, ItrsPosition


@dataclass(frozen=True, slots=True)
class RelativeItrsVector:
    """Station-to-satellite displacement in ITRS km at a scalar UTC epoch."""

    station: GroundStation
    _time_jd1: float
    _time_jd2: float
    vector_km: tuple[float, float, float]

    @property
    def time(self) -> Time:
        return Time(self._time_jd1, self._time_jd2, format="jd", scale="utc")


@dataclass(frozen=True, slots=True)
class EnuVector:
    """Station-to-satellite East, North, Up displacement in km."""

    station: GroundStation
    _time_jd1: float
    _time_jd2: float
    east_km: float
    north_km: float
    up_km: float

    @property
    def time(self) -> Time:
        return Time(self._time_jd1, self._time_jd2, format="jd", scale="utc")


def station_to_satellite_itrs(
    satellite: ItrsState, station_position: ItrsPosition
) -> RelativeItrsVector:
    """Subtract station ITRS position from satellite ITRS position at one epoch."""
    if not isinstance(satellite, ItrsState):
        raise TypeError("satellite must be an ItrsState")
    if not isinstance(station_position, ItrsPosition):
        raise TypeError("station_position must be an ItrsPosition")
    if satellite.time != station_position.time:
        raise ValueError("satellite and station observation times must match exactly")

    vector_km = tuple(
        satellite_component - station_component
        for satellite_component, station_component in zip(
            satellite.position_km, station_position.position_km, strict=True
        )
    )
    return RelativeItrsVector(
        station_position.station, satellite._time_jd1, satellite._time_jd2, vector_km
    )


def itrs_to_enu(relative: RelativeItrsVector) -> EnuVector:
    """Project ITRS displacement onto geodetic East, North, Up axes."""
    if not isinstance(relative, RelativeItrsVector):
        raise TypeError("relative must be a RelativeItrsVector")

    latitude = radians(relative.station.latitude_deg)
    longitude = radians(relative.station.longitude_deg)
    sin_lat, cos_lat = sin(latitude), cos(latitude)
    sin_lon, cos_lon = sin(longitude), cos(longitude)
    x, y, z = relative.vector_km
    east = -sin_lon * x + cos_lon * y
    north = -sin_lat * cos_lon * x - sin_lat * sin_lon * y + cos_lat * z
    up = cos_lat * cos_lon * x + cos_lat * sin_lon * y + sin_lat * z
    return EnuVector(relative.station, relative._time_jd1, relative._time_jd2, east, north, up)
