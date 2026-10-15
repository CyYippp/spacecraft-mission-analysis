"""Fixed WGS84 ground stations and their geocentric ITRS positions."""

from dataclasses import dataclass
from math import isfinite
from numbers import Real

import astropy.units as u
from astropy.coordinates import EarthLocation
from astropy.time import Time


@dataclass(frozen=True, slots=True)
class GroundStation:
    """WGS84 geodetic latitude, east longitude (degrees), ellipsoidal height (m)."""

    name: str
    latitude_deg: float
    longitude_deg: float
    height_m: float

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("station name must be nonempty")
        for label, value in (
            ("latitude_deg", self.latitude_deg),
            ("longitude_deg", self.longitude_deg),
            ("height_m", self.height_m),
        ):
            if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
                raise ValueError(f"{label} must be a finite number")
        if not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError("latitude_deg must be within [-90, 90]")
        if not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError("longitude_deg must be within [-180, 180]")


@dataclass(frozen=True, slots=True)
class ItrsPosition:
    """Geocentric station ITRS position in km at a scalar UTC epoch."""

    station: GroundStation
    _time_jd1: float
    _time_jd2: float
    position_km: tuple[float, float, float]

    @property
    def time(self) -> Time:
        """Return a fresh UTC time, preserving the immutable split JD."""
        return Time(self._time_jd1, self._time_jd2, format="jd", scale="utc")


def station_itrs_position(station: GroundStation, time: Time) -> ItrsPosition:
    """Convert WGS84 geodetic coordinates to geocentric ITRS km offline."""
    if not isinstance(station, GroundStation):
        raise TypeError("station must be a GroundStation")
    if not isinstance(time, Time) or not time.isscalar or time.scale != "utc":
        raise TypeError("time must be a scalar astropy.time.Time in UTC")

    location = EarthLocation.from_geodetic(
        lon=station.longitude_deg * u.deg,
        lat=station.latitude_deg * u.deg,
        height=station.height_m * u.m,
        ellipsoid="WGS84",
    )
    itrs = location.get_itrs(obstime=time)
    position_km = tuple(float(value) for value in itrs.cartesian.xyz.to_value(u.km))
    return ItrsPosition(station, time.jd1, time.jd2, position_km)
