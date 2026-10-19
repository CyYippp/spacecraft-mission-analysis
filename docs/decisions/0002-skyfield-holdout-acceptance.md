# 0002 — Skyfield Phase B hold-out acceptance criteria

Date: 2026-10-16. Status at criteria freeze: Phase B result and engineering
disposition pending. Affected requirements: MA-04 and MA-07. Scope: downstream
Skyfield access comparison with a shared SGP4 kernel.

Current execution status: the frozen Phase B hold-out subsequently **passed**;
see the [first-observed validation record](../validation.md#phase-b-first-observed-hold-out-result--pass).
The pre-execution wording below is retained as historical decision evidence.

## Decision question and previous proposal

What numerical agreement criteria should judge the unseen Phase B access
hold-out? The earlier provisional proposal was a **±2 s Skyfield access-event
comparison tolerance**. Phase A development characterization did not enforce
that proposal as an acceptance criterion.

## Reason, evidence, and alternatives

Phase A separated Skyfield's raw `find_events()` search timestamps from the
underlying 10° geometric threshold crossing. With matched Skyfield DUT1,
zero polar motion, and a shared `sgp4==2.27` propagation kernel, pointwise
elevation differed by at most `9.094947018e-13°`; ten ordinary refined
rise/set events differed by at most `0.002291132 s` (RMS `0.001348384 s`).
Raw search timestamps differed by up to roughly `0.1 s`. The raw timestamps
therefore measure event-discovery behaviour as well as crossing geometry.

Keeping ±2 s would be too loose for matched geometric crossings. Applying a
limit to raw `find_events()` times would test the search timestamps rather
than the refined crossings. Tightening the limit to the observed Phase A
maximum would overfit development data. The selected 20 ms limit instead
accounts for the numerical architecture: production Brent refinement uses
`xtol=0.01 s`, independent Skyfield bisection ends with a bracket width
`<=0.001 s`, checked DUT1 mismatch is `5.362377209e-14 s`, and Skyfield's
UTC epoch label differs by 14 µs. Near floating-point pointwise agreement
and millisecond Phase A timing residuals support this scale. The pointwise
`1e-9 deg` limit leaves numerical margin above the Phase A residual while
remaining sensitive to a material implementation mismatch.

## Frozen decision

- Retire the provisional ±2 s proposal. For each corresponding rise and set
  of an ordinary complete pass (Skyfield culmination `>=15°` with a 10° mask),
  require `abs(t_production - t_skyfield_bisected) <= 0.020 s` individually.
  Skyfield bisection is validation-only and independent of production Brent.
- On the predefined Phase B pointwise sample set, require
  `max(abs(elevation_production - elevation_skyfield)) <= 1e-9 deg`. The set is
  the interval endpoints and 300 s grid from the start, plus `−30, 0, +30 s`
  around each refined genuine Skyfield rise/set inside the interval, with
  duplicate timestamps removed.
- Require equal numbers of genuine in-interval rise and set crossings, their
  chronological rise/set order, and physically corresponding accesses.
  Clipped analysis boundaries do not count as crossings. An unmatched genuine
  crossing fails this count/order criterion and requires investigation.
- Report passes with `10° <` Skyfield culmination `<15°`, detection by both
  paths, and timing residuals when pairable. Classify these as near-threshold
  diagnostics and exclude them from the ordinary timing aggregate. A
  detection mismatch remains a visible detection-validation issue; its
  exclusion does not by itself fail the ordinary timing criterion. The
  separate count/order criterion still applies to unmatched genuine events.
- Retain `t_production - t_skyfield_raw` only as a diagnostic. Raw
  `find_events()` timestamps have no pass/fail role.

The timing and elevation limits measure **cross-implementation numerical
agreement**, not physical pass-time accuracy, TLE prediction accuracy,
operational navigation accuracy, physical angular accuracy, or knowledge of
the actual spacecraft crossing to 20 ms. Both paths share SGP4.

## Consequences and verification impact

MA-04 gains a frozen downstream event/geometry acceptance rule and MA-07 a
predeclared cross-implementation comparison rule. Neither gains a passing
Phase B result yet. The exact hold-out fixture and its sampling policy are
recorded in the [validation record](../validation.md). **Hold-out status:
defined and acceptance criteria frozen; not yet executed.** Phase A evidence,
production tolerances, runtime dependencies, and the engineering model
baseline remain unchanged. A later, separately reviewed Phase B run must
report the actual results and any unmatched or near-threshold events.
