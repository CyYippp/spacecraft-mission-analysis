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

## ISS-007 — EOP acquisition error escaped the frame boundary

- **Kind/status:** Observed software failure-path gap; resolved in the
  MA-05/06 run-contract increment.
- **Trigger/expectation/actual:** The frame service already raised
  `FrameTransformError` for an out-of-range IERS table, but an `OSError` while
  acquiring that table could escape before the availability check. The run
  contract requires unavailable EOP to become a structured failed result.
- **Consequence/cause:** Without conversion, a table-acquisition failure could
  bypass the `EOP_UNAVAILABLE` run record, although it still could not create
  a valid state or pass.
- **Disposition/retest:** The frame boundary now converts `OSError` and
  `ValueError` from table acquisition/query into `FrameTransformError`.
  [Scoped fault injection](../tests/test_run.py) verifies `FAILED`,
  `EOP_UNAVAILABLE`, and absent access/coverage. No EOP fallback or model
  convention changed.

## ISS-008 — cross-platform peak snapshot bytes

- **Kind/status:** Hosted-CI reproducibility discrepancy; snapshot assertion
  corrected on PR #10, with hosted checks as the retest gate.
- **Trigger/expectation/actual:** Both Ubuntu/Python 3.11 `verify` checks failed
  only at the archived JSON byte comparison in
  `test_archived_clean_run_is_byte_identical_and_complete`. Two reruns within
  each environment matched byte-for-byte, but Linux optimizer-derived peak
  elevations differed from the Windows-saved values by about `1e-14 deg`, and
  peak timestamps by nanoseconds. Entry/exit, duration, coverage,
  configuration, provenance and schema fields were unchanged in the logged diff.
- **Cause/consequence:** The bounded SciPy peak optimizer can return slightly
  different final floating-point values across platforms with the same pinned
  package versions. Treating those last bits as a cross-platform serialization
  acceptance oracle overstated the saved example's reproducibility.
- **Disposition/retest:** Keep exact byte comparison between independent
  same-environment runs, and exact saved-example comparison for every other
  JSON byte/CSV field. Check only the two peak fields against the *existing*
  MA-04 `1e-5 deg` and `0.02 s` criteria. The saved artifact, hashes, peak
  algorithm, physical model and numerical acceptance criteria remain unchanged.
  The corrected test must pass both hosted checks before closing this issue.

## ISS-009 — malformed TLE escaped the input boundary

- **Kind/status:** Observed input-validation defect; corrected in the MA-01
  archived-input increment.
- **Trigger/expectation/actual:** A 69-character TLE with a non-digit checksum
  column should be rejected, but `sgp4.io.verify_checksum()` skips that case;
  the previous `TleRecord` did not check the column itself. A syntactically
  shaped line 2 with zero mean motion could instead escape initialization as
  `ZeroDivisionError`, rather than a clear invalid-TLE error.
- **Consequence/cause:** Malformed archived input could pass the checksum gate
  or fail outside the project's input-error contract before scientific
  execution. Neither case is a valid SGP4 propagation result.
- **Correction/retest:** Require a numeric checksum column before calling the
  package checksum helper, and convert SGP4 parser/initialization arithmetic
  failure to `ValueError`. The versioned loader presents both as
  `InputConfigError`. [Independent corrupt-line fixtures](../tests/test_input.py)
  exercise both paths. Original lines are neither repaired nor normalized;
  no orbit model or physical acceptance criterion changed.
