# GMAT Phase B independent-dynamics diagnostic: frozen setup

This is a cross-model diagnostic, not an SGP4 accuracy or orbit-truth test.
Use the canonical Vanguard TLE and explicit archived EOP configuration. At
2000-06-27T20:00:00Z, compute production WGS72 SGP4 TEME state and convert it
with the Phase A validated Astropy TEME→GCRS implementation. Transfer the full
precision Cartesian state directly to GMAT `EarthICRF`; no STK ephemeris.

Before any propagation, GMAT must report that state back at the exact epoch.
The Euclidean position and velocity transfer residuals must be ≤1e-6 km and
≤1e-9 km/s. Stop if either fails.

The installed R2026a startup file maps `EGM96_FILE` to the bundled
`data/gravity/earth/EGM96.cof`; its ForceModel documentation permits the
`GravityField.Earth.PotentialFile` setting. Freeze Earth-only EGM96 degree 4,
order 4, tides None, drag None, SRP Off, point masses empty, relativistic
correction Off, no maneuvers. Do not derive physical drag properties from TLE
BSTAR. Integrate with PrinceDormand78, Accuracy 1e-12, InitialStepSize 10 s,
MinStep 0.001 s, MaxStep 60 s, and GMAT RSSStep error control. If GMAT rejects
any specified setting, stop; do not substitute a force model or integrator.

Report EarthICRF Cartesian position (km) and velocity (km/s) at 0, 5, …, 40
minutes. Run one refinement changing only MaxStep 60→30 s. At 40 minutes,
require base-minus-refined norms ≤0.001 km and ≤1e-6 km/s. Stop on failure.
For SGP4 versus GMAT, require finite and continuous sampled residuals with no
unexplained jumps, but set **no cross-model magnitude threshold**. Preserve
both full vectors and signed GMAT-minus-production residuals.

Only after the state diagnostic passes, use the same Phase A ContactLocator
stations, 10° mask, search settings, and Earth ellipsoid on the numerical
trajectory. Compare event count, AOS, LOS and duration to the archived
production result. Phase A timing criteria do not apply. Raw reports, console
output, scripts, hashes, and parsed CSV/JSON are evidence. No phase may be
rerun or tuned to improve agreement.
