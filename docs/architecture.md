# Architecture and implemented boundary

Planned pipeline:

```text
archived input / TLE
    → SGP4 orbit adapter [implemented M1a]
    → Astropy TEME-to-ITRS frame service [implemented and matched-case verified M1b]
    → WGS84 station ITRS → station-relative ITRS → ENU [implemented]
    → geometric azimuth/elevation/range [implemented]
    → elevation evaluator → coarse event search → bracketed root refinement
      → AccessWindow [implemented, internally verified]
    → temporal metrics and versioned outputs [future]
```

`src/spacecraft_mission_analysis/orbit.py` contains the M1a orbit module:

- `TleRecord` stores the exact TLE lines, optional source, catalogue ID, and
  UTC epoch. Construction validates fixed width, ASCII, checksums, matching
  catalogue IDs, and strict SGP4 field format.
- `Sgp4Propagator` owns the `Satrec` initialized with WGS72. `propagate()`
  accepts scalar UTC Astropy `Time`, passes its split Julian date to SGP4, and
  checks the returned status before constructing a state.
- `TemeState` labels the frame in its type and carries a UTC time, position in
  km, and velocity in km/s. `PropagationError` carries the SGP4 code and
  human-readable message.

`src/spacecraft_mission_analysis/frames.py` implements
`TemeState → Astropy TEME → Astropy ITRS → ItrsState`. It attaches both position
and velocity to the Astropy Cartesian representation, preserves the split UTC
time, and returns a typed Earth-fixed state in km and km/s. Astropy owns the
standards-level UT1, Earth-rotation, and polar-motion calculations. The frame
service checks EOP availability and raises `FrameTransformError` for unavailable
data; predicted EOP emits a warning.

The public states label their frames rather than exposing unlabeled six-element
arrays. Later geometry can depend on them without depending on `Satrec`. No
versioned output service exists yet. The frame service passes the
independent matched split-UT1 comparison at the frozen limits. The direct
published-vector comparison retains a documented 3.17 mm x-position overrun
from the numerical time-path mismatch.

`GroundStation` holds fixed WGS84 geodetic latitude, east-positive longitude,
and ellipsoidal height. `station_itrs_position()` uses Astropy
`EarthLocation.from_geodetic(..., ellipsoid="WGS84")` and `get_itrs(obstime=...)`
to return a typed `ItrsPosition` in km with the observation epoch and station
identity. `station_to_satellite_itrs()` subtracts this position from an
`ItrsState` at the **exact same UTC instant**, producing a station-to-satellite
`RelativeItrsVector`. `itrs_to_enu()` projects it onto the geodetic East,
North, Up basis and returns an `EnuVector` in km. `enu_to_az_el_range()` resolves
that typed vector into `AzElRange`: azimuth east of north in `[0°, 360°)`,
elevation above the horizon in `[−90°, +90°]`, and geometric range in km.
Azimuth is undefined (`None`) on the exact vertical axis. A zero-length vector
is rejected. No refraction or geoid conversion exists.

`elevation.py` composes these existing public interfaces at each requested UTC
time and exposes `satellite_elevation_deg()`. Its mission-level convenience
function defaults to a 10° mask. `access.py` depends only on a scalar elevation
callback, UTC start/end times, a configurable mask and sampling/refinement
settings; it does not import a TLE, propagator, frame, or station model. It
samples both analysis boundaries, finds positive-elevation intervals, and uses
SciPy `brentq` on elapsed seconds within each sign-changing bracket. An exact
sampled zero is used once as an endpoint. `AccessWindow` stores immutable split
UTC endpoints and derives duration in seconds. Clipped flags distinguish an
analysis bound from a threshold crossing. Upstream failures propagate.
