# Engineering issue and discrepancy register

This is the authoritative concise record of observed discrepancies, accepted
limitations, and documented design risks. Numerical evidence stays in
[verification](verification.md) and [validation](validation.md); engineering
reasoning for interview preparation belongs in the
[learning/fault log](engineering-learning-and-fault-log.md). An accepted limit
does not imply physical accuracy.

## ISS-001 — Vallado printed vector versus split UT1

- **Kind/status:** Observed discrepancy; bounded and dispositioned under
  [Decision 0001](decisions/0001-matched-split-ut1-frame-reference.md).
- **Trigger/expectation/actual:** Direct production comparison with the printed
  Appendix C ITRF vector exceeded the frozen `1e-5 km` per-component position
  limit in x by about 3.17 mm; velocity passed `1e-7 km/s`.
- **Consequence/cause:** The published-vector reproduction first rounds UTC to
  one Julian-date float, whereas production retains split UT1, giving different
  numerical UT1 instants. Exact historical print arithmetic is unavailable.
- **Disposition/retest:** Retain the direct discrepancy; use independent Vallado
  equations at matched split UT1 for active production acceptance, without
  changing limits or production physics. The matched position and velocity
  tests pass; see [verification](verification.md#active-matched-split-ut1-production-acceptance).

## ISS-002 — finite coarse-step detection

- **Kind/status:** Accepted numerical limitation; open for future access-scope
  review.
- **Trigger/expectation/actual:** A positive near-grazing interval `(1.8, 3.0) s`
  is missed on the 5 s sample grid; 1 s sampling detects it. A finite grid
  cannot guarantee discovery of every narrow interval.
- **Consequence/cause:** A real access shorter than the sampling gap could be
  omitted from an analysis; sign-change bracketing needs a sampled positive value.
- **Disposition/retest:** Preserve the 5 s baseline and disclose this detection
  limit. The [analytic test and result](verification.md#elevation-threshold-events)
  demonstrate both outcomes; no completeness guarantee is claimed.

## ISS-003 — shared SGP4 validation boundary

- **Kind/status:** Accepted validation limitation; independent propagation
  validation remains open under MA-07.
- **Trigger/expectation/actual:** Skyfield Phase A and frozen Phase B compare
  downstream geometry/events successfully, but both paths use `sgp4==2.27`.
- **Consequence/cause:** Their agreement cannot independently validate TLE
  propagation or physical pass-time accuracy.
- **Disposition/retest:** Scope the PASS to downstream numerical agreement;
  retain independent propagation/GMAT as future work. See
  [validation](validation.md#phase-b-first-observed-hold-out-result--pass).

## ISS-004 — raw Skyfield event-time distinction

- **Kind/status:** Observed comparison distinction; resolved by
  [Decision 0002](decisions/0002-skyfield-holdout-acceptance.md).
- **Trigger/expectation/actual:** Raw `find_events()` timestamps can differ from
  the actual geometric threshold crossing by about 0.1 s even when pointwise
  elevation and independently refined crossings agree closely.
- **Consequence/cause:** Raw search times include Skyfield event-discovery
  behaviour; treating them as crossing-time oracles would test the wrong quantity.
- **Disposition/retest:** Keep raw differences diagnostic only and compare
  validation-only bisected threshold crossings. The frozen Phase B criteria
  passed; see [validation](validation.md#phase-b-first-observed-hold-out-result--pass).

## ISS-005 — retired ±2 s proposal

- **Kind/status:** Prevented design risk; closed by
  [Decision 0002](decisions/0002-skyfield-holdout-acceptance.md). It was a
  provisional proposal, never a failed acceptance test.
- **Trigger/expectation/actual:** Phase A found millisecond-scale refined
  crossing differences under matched inputs, so ±2 s would have been too loose
  for the intended downstream numerical agreement check.
- **Consequence/cause:** Retaining that proposal could have hidden a material
  crossing implementation mismatch.
- **Disposition/retest:** Freeze 20 ms per ordinary refined event, `1e-9 deg`
  pointwise elevation, and genuine crossing order/count before Phase B exposure.
  The first-observed Phase B artifact passed these criteria; see
  [validation](validation.md#phase-b-first-observed-hold-out-result--pass).

## ISS-006 — peak-search globality boundary

- **Kind/status:** Accepted numerical limitation; independent peak validation
  remains open under MA-04.
- **Trigger/expectation/actual:** Bounded optimization and comparison of both
  endpoints, sampled values and grid-visible local peaks recover the analytic
  fixtures, including a two-peak window. A finite 5 s grid cannot certify an
  arbitrarily narrow unsampled higher peak within an otherwise detected window.
- **Consequence/cause:** Reported peak elevation/time could miss such a feature;
  scalar bounded search alone has no global guarantee for arbitrary multimodal
  callbacks.
- **Disposition/retest:** Scope the result to smooth, resolved access passes.
  Keep the [analytic and archived integration evidence](verification.md#maximum-elevation-within-detected-access-windows)
  and disclose the limit. No hidden-peak completeness or physical peak-time
  claim is made; broader adaptive/global search needs separate scope/evidence.
