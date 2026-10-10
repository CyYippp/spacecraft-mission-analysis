"""TEME to ITRS transformation with explicit Earth-orientation inputs."""

import warnings
from dataclasses import dataclass
from math import isfinite

import astropy.units as u
from astropy.coordinates import ITRS, TEME, CartesianDifferential, CartesianRepresentation
from astropy.time import Time
from astropy.utils import iers

from .orbit import TemeState


@dataclass(frozen=True, slots=True)
class ItrsState:
    """ITRS position in km and velocity in km/s at scalar UTC time."""

    _time_jd1: float
    _time_jd2: float
    position_km: tuple[float, float, float]
    velocity_km_s: tuple[float, float, float]

    @property
    def time(self) -> Time:
        """Return a fresh UTC Time so the frozen state cannot be mutated through it."""
        return Time(self._time_jd1, self._time_jd2, format="jd", scale="utc")


class FrameTransformError(RuntimeError):
    """Earth-orientation data cannot support the requested frame transform."""


def _check_earth_orientation(time: Time) -> None:
    table = iers.earth_orientation_table.get()
    ut1_utc, ut1_status = table.ut1_utc(time, return_status=True)
    xp, yp, polar_status = table.pm_xy(time, return_status=True)
    if (
        ut1_status < 0
        or polar_status < 0
        or not all(isfinite(value) for value in (ut1_utc.value, xp.value, yp.value))
    ):
        raise FrameTransformError(f"Earth-orientation data unavailable at {time.utc.isot} UTC")
    if ut1_status == iers.FROM_IERS_A_PREDICTION or polar_status == iers.FROM_IERS_A_PREDICTION:
        warnings.warn(
            f"Predicted Earth-orientation data used at {time.utc.isot} UTC",
            UserWarning,
            stacklevel=2,
        )


def teme_to_itrs(state: TemeState) -> ItrsState:
    """Transform one TEME Cartesian state using Astropy's IERS-backed ITRS frame."""
    if not isinstance(state, TemeState):
        raise TypeError("state must be a TemeState")

    time = state.time
    _check_earth_orientation(time)
    position = CartesianRepresentation(u.Quantity(state.position_km, u.km))
    velocity = CartesianDifferential(u.Quantity(state.velocity_km_s, u.km / u.s))
    teme = TEME(position.with_differentials(velocity), obstime=time)
    itrs = teme.transform_to(ITRS(obstime=time))
    position_km = tuple(float(value) for value in itrs.cartesian.xyz.to_value(u.km))
    velocity_km_s = tuple(
        float(value) for value in itrs.cartesian.differentials["s"].d_xyz.to_value(u.km / u.s)
    )
    return ItrsState(time.jd1, time.jd2, position_km, velocity_km_s)
