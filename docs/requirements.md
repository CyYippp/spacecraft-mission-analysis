# Requirements and current disposition

Source baseline: `01-spacecraft-mission-analysis.md` in the portfolio plans.
The M1a implementation covers only the archived-TLE/SGP4 boundary. Later
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
  **Not started.** No verification claim.
- **MA-04 — Access events.** Detect and refine threshold crossings, pass
  duration, and maximum elevation. **Not started.** No verification claim.
- **MA-05 — Versioned outputs and provenance.** Produce machine-readable
  results with units, UTC timestamps, configuration, and source history.
  **Not started.** The M1a fixture records test provenance only.
- **MA-06 — Warnings and failures.** Make invalid propagation and later stale
  TLE, unsupported interval, or unavailable Earth-orientation conditions
  explicit. **M1a partial:** propagation failure is explicit and blocks state
  return. Other warnings are future work.
- **MA-07 — Independent comparison.** Compare agreed cases with an independent
  implementation and later GMAT under matched modelling assumptions.
  **Not started.** The current package fixture is same-model verification.
- **MA-08 — Temporal station coverage.** Calculate coverage and no-access gaps
  from validated access intervals. **Not started.** No verification claim.

The [verification record](verification.md) identifies current evidence. The
[validation record](validation.md) separates current integration evidence from
future mission-analysis validation.
