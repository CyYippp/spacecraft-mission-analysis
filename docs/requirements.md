# Requirements and current disposition

Source baseline: `01-spacecraft-mission-analysis.md` in the portfolio plans.
M1a covers the archived-TLE/SGP4 boundary, and M1b adds the frame boundary. Later
acceptance thresholds must be declared before their verification runs.

- **MA-01 — Archived TLE input.** Preserve original lines, epoch, catalogue ID,
  and available source metadata; reject malformed or inconsistent lines.
  **M1a partial:** exact lines, UTC epoch, catalogue ID, optional source,
  checksum/format/identity checks are implemented in `TleRecord`. A run-level
  input manifest is future work. Evidence: `tests/test_orbit.py` TLE tests.
- **MA-02 — SGP4 propagation.** Use a pinned SGP4 implementation, explicit
  gravity constants, and report failures and time since epoch. **M1a partial:**
  WGS72 propagation, typed TEME state, reference-vector verification, and
  explicit SGP4 errors exist. Run-level elapsed-time reporting is future work.
  Evidence: `tests/test_orbit.py` vector and error tests.
- **MA-03 — Frames and topocentric geometry.** Convert TEME to an Earth-fixed
  frame and station azimuth/elevation/range with declared conventions.
  **M1b partial:** TEME→ITRS position and velocity conversion is implemented.
  Both pass the frozen limits against an independent matched split-UT1 Vallado
  calculation. The printed Appendix C x position remains 3.17 mm over the
  10 mm limit when compared directly with production; its numerical reference
  path is separately reproduced. **Station/ENU partial:** fixed WGS84 station
  ITRS position, station-to-satellite ITRS displacement, and local ENU components
  are implemented and numerically checked. **Look-angle increment:** geometric
  azimuth, elevation, and range are implemented and analytically checked, with
  undefined vertical azimuth represented explicitly. MA-03's component chain
  is implemented; satellite-access validation remains future work. Evidence:
  `tests/test_frames.py`, `tests/test_station_enu.py`, `tests/test_look_angles.py`,
  and their verification records.
- **MA-04 — Access events.** Detect and refine threshold crossings, pass
  duration, and maximum elevation. **Partial:** the configurable scalar
  elevation-threshold solver detects sampled entry/exit brackets, refines them
  with local-second Brent roots, and returns typed windows with derived
  duration and clipped-boundary flags. Analytic and internal archived-orbit
  tests pass. Maximum elevation and independent access validation remain future
  work. Evidence: `tests/test_access.py`, `tests/test_access_integration.py`.
- **MA-05 — Versioned outputs and provenance.** Produce machine-readable
  results with units, UTC timestamps, configuration, and source history.
  **Not started.** The M1a fixture records test provenance only.
- **MA-06 — Warnings and failures.** Make invalid propagation and later stale
  TLE, unsupported interval, or unavailable Earth-orientation conditions
  explicit. **M1a partial:** propagation failure is explicit and blocks state
  return. **M1b partial:** unavailable EOP raises `FrameTransformError`; predicted
  EOP warns. Other warnings are future work.
- **MA-07 — Independent comparison.** Compare agreed cases with an independent
  implementation and later GMAT under matched modelling assumptions.
  **Partial evidence:** M1b passes an independent matched split-UT1 Vallado
  equation reference, and the printed vector is separately reproduced by the
  historical single-JD path. The direct printed-vector x discrepancy remains
  recorded. Independent end-to-end implementation and GMAT comparisons are
  future work. The M1a package fixture is same-model verification.
- **MA-08 — Temporal station coverage.** Calculate coverage and no-access gaps
  from validated access intervals. **Not started.** No verification claim.

The [verification record](verification.md) identifies current evidence. The
[validation record](validation.md) separates current integration evidence from
future mission-analysis validation.
