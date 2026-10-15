"""Station-relative ITRS displacement and local geodetic ENU projection."""

from dataclasses import dataclass
from math import atan2, cos, degrees, hypot, isfinite, radians, sin

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


@dataclass(frozen=True, slots=True)
class AzElRange:
    """Geometric azimuth/elevation in degrees and station range in km.

    Azimuth is east of north in [0, 360), or None on the exact vertical axis.
    Elevation is above the local horizon in [-90, 90].
    """

    station: GroundStation
    _time_jd1: float
    _time_jd2: float
    azimuth_deg: float | None
    elevation_deg: float
    range_km: float

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


def enu_to_az_el_range(enu: EnuVector) -> AzElRange:
    """Resolve a nonzero ENU displacement into geometric azimuth, elevation, range."""
    if not isinstance(enu, EnuVector):
        raise TypeError("enu must be an EnuVector")
    east, north, up = enu.east_km, enu.north_km, enu.up_km
    if not all(isfinite(value) for value in (east, north, up)):
        raise ValueError("ENU components must be finite")

    horizontal_km = hypot(east, north)
    range_km = hypot(horizontal_km, up)
    if not isfinite(range_km) or range_km == 0.0:
        raise ValueError("ENU vector must have a finite nonzero range")

    azimuth_deg = None if horizontal_km == 0.0 else degrees(atan2(east, north)) % 360.0
    elevation_deg = degrees(atan2(up, horizontal_km))
    return AzElRange(
        enu.station, enu._time_jd1, enu._time_jd2, azimuth_deg, elevation_deg, range_km
    )
