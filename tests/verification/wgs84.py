"""Direct WGS84 equations for independent station-position verification.

Constants: NGA WGS 84 defining parameters, a = 6378137.0 m and 1/f =
298.257223563 (https://earth-info.nga.mil/index.php?action=wgs84&dir=wgs84).
This module does not call Astropy's geodetic conversion.
"""

from math import cos, radians, sin, sqrt

A_M = 6378137.0
INVERSE_FLATTENING = 298.257223563
FLATTENING = 1.0 / INVERSE_FLATTENING
B_M = A_M * (1.0 - FLATTENING)


def geodetic_to_itrs_km(
    latitude_deg: float, longitude_deg: float, height_m: float
) -> tuple[float, float, float]:
    """Evaluate the WGS84 geodetic-to-Cartesian equations in km."""
    latitude = radians(latitude_deg)
    longitude = radians(longitude_deg)
    sin_lat, cos_lat = sin(latitude), cos(latitude)
    e2 = FLATTENING * (2.0 - FLATTENING)
    prime_vertical_radius_m = A_M / sqrt(1.0 - e2 * sin_lat**2)
    x_m = (prime_vertical_radius_m + height_m) * cos_lat * cos(longitude)
    y_m = (prime_vertical_radius_m + height_m) * cos_lat * sin(longitude)
    z_m = (prime_vertical_radius_m * (1.0 - e2) + height_m) * sin_lat
    return x_m / 1000.0, y_m / 1000.0, z_m / 1000.0
