"""Independent Vallado/Skyfield TEME-to-ITRF equations for Appendix C tests.

The evaluation order follows Skyfield commit 31a6ed7584cd09b6e48e07546a4b5921e1cd5bb4:
``skyfield/sgp4lib.py`` and ``skyfield/timelib.py``. No production frame code or
Astropy high-level frame transformation is used here.
"""

from math import cos, pi, sin
from typing import Sequence

import numpy as np


def gmst1982(jd_ut1: float, fraction_ut1: float = 0.0) -> tuple[float, float]:
    """Return Vallado GMST angle in radians and angular rate in radians/day."""
    t = (jd_ut1 - 2451545.0 + fraction_ut1) / 36525.0
    g = 67310.54841 + (8640184.812866 + (0.093104 - 6.2e-6 * t) * t) * t
    dg = 8640184.812866 + (2.0 * 0.093104 - 3.0 * 6.2e-6 * t) * t
    theta = (jd_ut1 % 1.0 + fraction_ut1 + g / 86400.0 % 1.0) % 1.0 * (2.0 * pi)
    theta_dot = (1.0 + dg / (86400.0 * 36525.0)) * (2.0 * pi)
    return theta, theta_dot


def teme_to_itrf_vallado(
    jd_ut1: float,
    fraction_ut1: float,
    position_km: Sequence[float],
    velocity_km_s: Sequence[float],
    xp_arcsec: float,
    yp_arcsec: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Transform TEME km and km/s to ITRF km and km/s using Vallado equations."""
    theta, theta_dot = gmst1982(jd_ut1, fraction_ut1)
    xp = xp_arcsec * pi / (180.0 * 3600.0)
    yp = yp_arcsec * pi / (180.0 * 3600.0)
    rz = np.array([[cos(theta), sin(theta), 0.0], [-sin(theta), cos(theta), 0.0], [0.0, 0.0, 1.0]])
    ry = np.array([[cos(xp), 0.0, sin(xp)], [0.0, 1.0, 0.0], [-sin(xp), 0.0, cos(xp)]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cos(yp), -sin(yp)], [0.0, sin(yp), cos(yp)]])
    rpef = rz @ np.asarray(position_km)
    vpef = rz @ np.asarray(velocity_km_s)
    vpef -= np.cross([0.0, 0.0, theta_dot / 86400.0], rpef)
    polar_motion = rx @ ry
    return polar_motion @ rpef, polar_motion @ vpef
