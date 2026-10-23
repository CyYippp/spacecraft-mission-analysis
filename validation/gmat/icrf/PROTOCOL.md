# GMAT R2026a ICRF transfer trial — frozen protocol

Date frozen: 2026-10-23, before any Astropy–Skyfield transfer residual or
ICRF STK file was generated. This is validation-only work on the archived
Vanguard TLE in `examples/vanguard_run/config.json`; production remains
TEME→ITRS. The installed R2026a `EphemerisFile.html` and `Propagator.html`
document Earth STK `ICRF` support. The earlier STK `Fixed` gate failed; retain
all evidence in `../fixed_gate_diagnostic/`.

## Transfer convention and first gate

Propagate the archived TLE with the production WGS72 SGP4 adapter. Attach its
TEME position and velocity to Astropy `TEME(obstime=UTC)` and transform to
`GCRS(obstime=same UTC)` with the canonical config's explicit EOP snapshot
scoped in Astropy and network download disabled. Astropy's graph may pass
through Earth-fixed frames; this EOP input is part of the documented frame
transformation, not a new force or orbit model. GCRS is geocentric with axes
aligned to ICRS. We provisionally map its Cartesian coordinates to the STK
`ICRF` Earth-centered representation; this is a transfer convention, not a
claim that GCRS and every ICRF implementation are mathematically identical.

At 2000-06-27 19:59:00, 20:00:00, 20:20:00, 20:40:00, and 20:41:00 UTC,
compare the Astropy state against `skyfield.EarthSatellite.at()` geocentric
inertial position/velocity from the same TLE. Skyfield uses the same SGP4
kernel, so this checks only the conversion implementation. Require Euclidean
position residual ≤0.001 km and velocity residual ≤1e-6 km/s at **each** time.
Record every vector and residual, versions, input identities, and status. These
are numerical transfer limits, not physical orbit accuracy. Stop on any fail;
do not tune after seeing results.

## Conditional GMAT gates

Only if the first gate passes, generate a 1.0 s STK `CoordinateSystem ICRF`
EphemerisTimePosVel file from 19:59 through 20:41 UTC inclusive, with Earth
central body and km/km/s. Preserve generator, file, SHA-256, and convention.

Gate 2: `GetEphemStates()` in `EarthICRF` must reproduce both file endpoints,
each with position norm ≤1e-6 km and velocity norm ≤1e-9 km/s. A report-
precision failure is a failure to resolve before proceeding, not grounds to
relax the threshold.

Gate 3: GMAT STK propagation at exact grid times 20:00, 20:20, 20:40 UTC
must match the corresponding file rows in `EarthICRF` with the same limits.
Stop at the first failed gate; do not try another transfer frame.

If gates 1–3 pass, compare imported `EarthFixed` and production ITRS states
at one or more epochs as a diagnostic only. Record each EOP source and frame
theory difference. Only then may the already frozen Phase A ContactLocator
protocol resume: same genuine event count/order, each AOS/LOS ≤0.25 s,
duration ≤0.50 s, and 1.0-versus-0.5 s ephemeris event shift ≤0.02 s.
No Phase B or ContactLocator run is authorized before the transfer gates pass.
