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
  The Vallado velocity and two position components meet their frozen limits;
  one position component is 3.17 mm over its 10 mm limit. Station/topocentric
  geometry is future work. Evidence: `tests/test_frames.py` and the frame
  fixture discrepancy record.
- **MA-04 — Access events.** Detect and refine threshold crossings, pass
  duration, and maximum elevation. **Not started.** No verification claim.
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
  **Partial evidence:** the M1b frame output is compared with an independent
  published Vallado example, with one unresolved position residual. Independent
  end-to-end implementation and GMAT comparisons are future work. The M1a
  package fixture is same-model verification.
- **MA-08 — Temporal station coverage.** Calculate coverage and no-access gaps
  from validated access intervals. **Not started.** No verification claim.

The [verification record](verification.md) identifies current evidence. The
[validation record](validation.md) separates current integration evidence from
future mission-analysis validation.
