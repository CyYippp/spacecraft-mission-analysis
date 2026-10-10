# Architecture and implemented boundary

Planned pipeline:

```text
archived input / TLE
    → SGP4 orbit adapter [implemented M1a]
    → TEME-to-Earth-fixed frame service [future]
    → fixed-station/topocentric geometry [future]
    → access-event solver [future]
    → temporal metrics and versioned outputs [future]
```

`src/spacecraft_mission_analysis/orbit.py` contains the only implemented
engineering module:

- `TleRecord` stores the exact TLE lines, optional source, catalogue ID, and
  UTC epoch. Construction validates fixed width, ASCII, checksums, matching
  catalogue IDs, and strict SGP4 field format.
- `Sgp4Propagator` owns the `Satrec` initialized with WGS72. `propagate()`
  accepts scalar UTC Astropy `Time`, passes its split Julian date to SGP4, and
  checks the returned status before constructing a state.
- `TemeState` labels the frame in its type and carries a UTC time, position in
  km, and velocity in km/s. `PropagationError` carries the SGP4 code and
  human-readable message.

The public orbit result is a frame-specific state rather than an unlabeled
six-element array. Later geometry can depend on that state boundary without
depending on `Satrec`. No frame, station, event, or output service exists yet.
