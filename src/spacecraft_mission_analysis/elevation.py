"""Compose the verified orbit, frame, station, and look-angle interfaces."""

from astropy.time import Time

from .access import AccessWindow, find_access_windows
from .frames import teme_to_itrs
from .geometry import enu_to_az_el_range, itrs_to_enu, station_to_satellite_itrs
from .orbit import Sgp4Propagator
from .stations import GroundStation, station_itrs_position


def satellite_elevation_deg(
    propagator: Sgp4Propagator, station: GroundStation, time: Time
) -> float:
    """Geometric elevation in degrees; upstream failures remain explicit."""
    satellite_itrs = teme_to_itrs(propagator.propagate(time))
    station_itrs = station_itrs_position(station, time)
    relative = station_to_satellite_itrs(satellite_itrs, station_itrs)
    return enu_to_az_el_range(itrs_to_enu(relative)).elevation_deg


def find_satellite_access_windows(
    propagator: Sgp4Propagator,
    station: GroundStation,
    start: Time,
    end: Time,
    *,
    minimum_elevation_deg: float = 10.0,
    coarse_step_s: float = 5.0,
    root_tolerance_s: float = 0.01,
) -> tuple[AccessWindow, ...]:
    """Apply the mission-level default mask to the general event solver."""
    return find_access_windows(
        lambda time: satellite_elevation_deg(propagator, station, time),
        start,
        end,
        minimum_elevation_deg=minimum_elevation_deg,
        coarse_step_s=coarse_step_s,
        root_tolerance_s=root_tolerance_s,
    )
