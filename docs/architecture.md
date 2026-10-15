# Architecture and implemented boundary

Planned pipeline:

```text
archived input / TLE
    → SGP4 orbit adapter [implemented M1a]
    → Astropy TEME-to-ITRS frame service [implemented and matched-case verified M1b]
    → fixed-station/topocentric geometry [future]
    → access-event solver [future]
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
station, event, or output service exists yet. The frame service passes the
independent matched split-UT1 comparison at the frozen limits. The direct
published-vector comparison retains a documented 3.17 mm x-position overrun
from the numerical time-path mismatch.
