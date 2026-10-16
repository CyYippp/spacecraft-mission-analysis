# Changelog

## Unreleased

- Froze Phase B Skyfield hold-out acceptance before execution: 20 ms per
  ordinary refined rise/set, `1e-9 deg` maximum pointwise elevation difference,
  and genuine crossing count/order agreement. Retired the provisional ±2 s
  proposal; near-threshold and raw-search events retain diagnostic status.
  Phase A characterization and the unexecuted hold-out fixture are unchanged.
- Added Phase A Skyfield development-case comparison with bundled-timescale
  DUT1 matched into scoped Astropy IERS data, zero polar motion, pointwise
  geometric elevation checks, Skyfield event discovery, and validation-only
  bisection. Skyfield is an optional validation dependency; the shared SGP4
  kernel and unexecuted hold-out are explicit.
- Added configurable elevation-threshold access windows with 5 s default
  sampling, local-second Brent refinement at 0.01 s, clipped-boundary flags,
  and an internal archived-orbit smoke test. Analytic event verification is
  separate from future independent access validation.
- Added typed geometric azimuth/elevation/range output from ENU, with explicit
  undefined azimuth on the vertical axis and a failure for zero displacement.
  Analytic direction, horizon, zenith/nadir, quadrant, and range checks pass.
- Added fixed WGS84 ground stations, typed station ITRS positions, typed
  station-to-satellite ITRS displacements, and explicit geodetic ENU projection.
  Verified against NGA-parameter WGS84 equations and analytic/synthetic ENU
  cases. Access events remain future.
- Added M1b Astropy TEME-to-ITRS position/velocity conversion with an immutable
  ITRS state and explicit Earth-orientation failure/warning policy.
- Added a scoped, offline Vallado Appendix C comparison. The direct
  production-minus-printed x-position residual exceeds the 10 mm limit by
  3.17 mm and remains recorded as a numerical reference discrepancy.
- Diagnosed that Skyfield's single-JD Appendix C path reproduces the printed
  vector, while its split-UT1 path agrees with Astropy.
- Approved a verification-reference change: the printed vector is retained as
  historical reproduction evidence, and an independent matched split-UT1
  calculation is the active production acceptance reference. The original
  10 mm position and 0.1 mm/s velocity limits remain unchanged; no production
  physics or frame code changed.

## M1a orbit kernel and repository setup

- Established source, test-fixture, documentation, and CI structure.
- Implemented validation of archived TLE lines and explicit WGS72 SGP4
  propagation to a typed TEME state in km and km/s.
- Added a package reference-vector test and explicit propagation-error checks.
- Added engineering status and evidence records without claiming frame or
  access functionality.
