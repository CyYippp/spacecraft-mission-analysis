# Assumptions and boundaries

- Inputs are **archived TLEs only**. One spacecraft is propagated per analysis;
  the current adapter handles one scalar time per call.
- A TLE contains **SGP4 mean elements**, not generic osculating elements. It
  is propagated by `python-sgp4`, not a two-body Keplerian reconstruction.
- The orbit kernel explicitly uses **WGS72** constants. Its Cartesian output
  is **TEME**, with position in **km** and velocity in **km/s**.
- Computational time is scalar Astropy `Time` on the **UTC** scale. The core
  rejects direct Python datetimes, including naive ones. It passes split
  `jd1`/`jd2` values to SGP4 without hidden unit or frame conversion.
- The archived M1a reference case checks reproduction of a published/package
  SGP4 vector. It is **not** a measurement of physical-orbit truth or TLE
  prediction uncertainty.
- Astropy 7.2.1 supplies the TEME-of-date to ITRS conversion. The output is an
  Earth-centred, Earth-fixed `ItrsState` in km and km/s at exactly the input UTC
  epoch. Astropy applies its Vallado-compatible 1982 sidereal-time convention
  and Earth-orientation data; the project supplies neither a custom rotation
  nor custom velocity correction.
- ITRS conversion depends on UT1−UTC and polar motion from an IERS table.
  Normal analysis retains Astropy's automatic IERS download setting (enabled
  by default) and any relevant Astropy warnings. The adapter rejects missing
  or out-of-range EOP and warns when using predicted EOP. Formal tests disable
  downloads only in scoped contexts and inject the published EOP for the
  Vallado frame case; global settings are restored after each test. The
  archived Vanguard run selects its own separate test-only EOP table through
  its config file.
- Fixed stations use the **WGS84 ellipsoid**, separately from SGP4's WGS72
  gravity constants. Latitude is **geodetic** (the ellipsoid-normal direction),
  longitude is **east-positive** in `[-180°, +180°]`, and height is **ellipsoidal**
  metres, including possible negative values. No geoid or mean-sea-level
  conversion is performed. Station ITRS position is geocentric and in km.
- The station-relative ITRS vector points **station → satellite** at one exact
  scalar UTC instant. Local Up follows the WGS84 geodetic ellipsoid normal,
  not the geocentric radial direction. At an exact pole, supplied longitude
  selects the local East/North basis; azimuth at an exact pole therefore follows
  the supplied longitude convention and is not physically unique there. The
  ENU output contains km components.
- Geometric azimuth is measured clockwise/eastward from local North in
  `[0°, 360°)`; elevation is above the local horizon in `[−90°, +90°]`; range is
  the Euclidean station-to-satellite displacement in km. Azimuth is `None`
  when both horizontal ENU components are exactly zero (zenith or nadir). There
  is no hidden near-zenith threshold. A zero-length displacement has no viewing
  direction and raises an error. No atmospheric refraction is applied.
- Access is the set of times with geometric elevation **strictly greater than**
  the minimum elevation. Equality is a boundary, not positive access. The
  mission-level default mask is 10°, and callers may configure it. The generic
  numerical solver has no fixed mask.
- Normal event search samples every 5 s, includes exact analysis boundaries,
  and refines sign-changing brackets with SciPy `brentq` using elapsed seconds
  from a bracket endpoint and `xtol=0.01 s`. This tolerance controls numerical
  root refinement only; it does not establish physical pass-time, TLE, frame,
  or station-coordinate accuracy. A finite grid cannot guarantee discovery of
  arbitrarily narrow or near-grazing positive intervals. A sampled tangent
  touching the threshold from below creates no access.
- A window beginning or ending while elevation is already above the mask is
  clipped at that analysis boundary; no event outside the requested interval
  is inferred. Endpoint times denote threshold crossings or clipped bounds;
  access itself is strict `elevation > mask`, so equality endpoints need not
  be members of the positive set. Duration is the endpoint time difference.
- Peak elevation is evaluated over each reported closed endpoint interval,
  including clipped boundaries. Bounded scalar refinement uses seconds from
  the local window start with `xatol=0.002 s`; this is a numerical setting, not
  physical time accuracy. The solver compares both boundaries, all existing
  detection-grid samples, a full-window candidate, and locally refined sampled
  peaks. Exact equal-elevation ties retain the earliest candidate time.
  Flat or nearly flat peaks can have weakly identifiable timestamps. As with
  access detection, finite sampling cannot certify a hidden narrow peak or an
  arbitrary multimodal function's global maximum.
- Temporal station coverage is measured over a stated `[start, end]` UTC
  analysis span. Supplied access intervals are clipped to that span; isolated
  endpoint instants and zero-duration contacts contribute no elapsed time.
  Overlapping and exactly touching intervals are merged, since a shared
  endpoint is no positive-duration outage. `access_window_count` is the number
  of merged union intervals, not the sum of per-station passes. Equal longest
  no-access gaps select the earliest. Coverage fraction is accessible duration
  divided by strictly positive analysis duration. This is temporal availability
  of at least one station, not geographic sensor coverage.
- The internal orbit smoke fixture uses a synthetic fixed equator/Greenwich
  WGS84 station and a test-only zero-valued EOP table at MJD 51722–51723. It
  demonstrates software integration only, not realistic EOP or independent
  prediction accuracy. The archived run config explicitly selects its
  relative-path fixture and records the loaded content hash; ordinary runs
  use configured Astropy IERS data without a synthetic fallback. Atmospheric
  refraction, terrain masks, link margin,
  eclipse, and geographic sensor footprint require separate scope and evidence.
- TLE prediction quality can degrade with age. Staleness warnings and a
  supported analysis interval were not defined in M1a. The run layer now emits
  `TLE_AGE_WARNING` when the maximum absolute analysis-bound offset from TLE
  epoch exceeds **7 days**. This is a conservative workflow heuristic, not a
  calibrated uncertainty or guaranteed physical accuracy boundary. Younger
  TLEs are not certified accurate; orbit and environment matter. A run may
  complete with this warning if its calculations succeed.
- A run longer than **24 hours** emits
  `ANALYSIS_SPAN_OUTSIDE_VALIDATED_ENVELOPE`: current comparison evidence
  exercised 24-hour cases, so a longer span exceeds that duration envelope.
  The threshold is neither a physical SGP4 accuracy limit nor a computational
  rejection rule. Both warnings and their numerical thresholds are preserved
  in the run output. Required EOP or SGP4 failure instead marks the run
  `FAILED` and suppresses all access and coverage results. Genuine no-pass
  output is a successful run with zero coverage.
