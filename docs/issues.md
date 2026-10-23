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

## ISS-010 — named EOP source without reproducible input

- **Kind/status:** Observed run-provenance/reproducibility defect; corrected in
  the explicit-EOP input increment.
- **Trigger/expectation/actual:** The canonical Vanguard config named a
  test-only zero-UT1/polar-motion source but did not provide its table to
  `load_analysis_config()` or `run_analysis()`. Tests injected the file through
  a separate Astropy context. With ordinary configured IERS data, the same
  config returned `SUCCESS` yet accessible duration was
  `1229.2219018011551 s` instead of the saved `1229.2680210995704 s`, and
  the first rise was about `0.048487 s` later.
- **Consequence/cause:** A source label described intended provenance but was
  not executable model input. The archived input was not self-contained and
  its saved scientific result could not be reproduced from the config alone.
- **Correction/retest:** Input schema 1.1 requires `configured_iers` or
  `explicit_table`. The archived config references its test-only file relative
  to itself; the loader snapshots validated values and SHA-256, and the run
  boundary scopes that table without changing the frame transform. Run schema
  1.1 records mode, source, relative identity and hash. The direct config→run
  test now matches the archived scientific values under the existing PR #10
  peak rules. Review found that host-only absolute-path validation admitted
  Windows rooted and drive-relative syntax; the loader now rejects POSIX roots
  and Windows roots/drives on every host before file access, with expected path
  errors reported as `InputConfigError`. Ordinary configured-IERS and MA-06
  fail-closed paths remain.

## ISS-011 — escaped surrogate bypassed portable output text validation

- **Kind/status:** Review-discovered CLI/input-contract defect; corrected on
  the CLI branch.
- **Trigger/expectation/actual:** JSON can validly escape a lone surrogate in
  `source_revision`. The loader previously accepted any nonempty string; CSV
  UTF-8 writing then raised `UnicodeEncodeError` outside the CLI's output
  `OSError` mapping, producing a traceback and process exit `1`.
- **Correction/retest:** The shared input-text validator rejects strings that
  cannot encode as UTF-8, returning `InputConfigError` before analysis. The CLI
  now reports a concise input error and exits `2` with no output. Tests cover
  every free-text input field and show that valid non-ASCII text remains valid.
  No scientific value, schema version, or output-failure exit rule changed.

## ISS-012 — GMAT STK transfer failed same-state compatibility gates

- **Kind/status:** Observed MA-07 validation-transfer discrepancy. Historical
  failed gates and raw evidence retained; corrected ICRF transfer method
  subsequently qualified for Phase A. The Fixed import mechanism remains
  unexplained.
- **Fixed path:** GMAT R2026a accepted the STK `Fixed` file syntactically, but
  its propagated 20:00 EarthFixed state differed from production ITRS by
  `0.734178219 km`, almost exactly a one-sidereal-second Z rotation. Time,
  leap-second, direct-state and EOP controls did not explain the inter-path
  residual. The internal cause is not established. The `Fixed` transfer was
  rejected, with raw evidence retained in
  [the diagnostic](../validation/gmat/fixed_gate_diagnostic/README.md).
- **ICRF trial:** Installed R2026a help documents STK ICRF for Earth. A
  validation-only Astropy TEME→GCRS conversion agreed with Skyfield's
  geocentric inertial conversion at all five frozen times (position maximum
  `1.424365e-7 km`, velocity maximum `7.999170e-8 km/s`), below `0.001 km`
  and `1e-6 km/s`. GMAT `GetEphemStates(..., EarthICRF)` reproduced both
  serialized endpoints within `1e-6 km` and `1e-9 km/s`. At the exact 20:00,
  20:20 and 20:40 file-grid epochs, GMAT STK-propagated velocity differed
  from the serialized rows by `0.001141886`, `0.000448212` and
  `0.000401191 km/s`; the frozen limit is `1e-9 km/s`. Position also exceeded
  its `1e-6 km` limit at 20:20 and 20:40. The sample gate failed and ICRF is
  not approved for ContactLocator **under that original gate**. The precise
  mechanism is not established.
  See the [trial evidence](../validation/gmat/icrf/README.md) and
  [Decision 0003](decisions/0003-gmat-icrf-transfer-trial.md).
- **Immediate consequence:** ContactLocator, EarthFixed diagnostic, Phase B
  and alternate transfer-frame trials stopped at the failed original gate.
  Production analysis, frozen event limits and MA-07 status remained unchanged.
- **Validation-method review:** The installed R2026a STK propagator guide
  states that default position interpolation uses a seventh-order
  Hermite-Newton polynomial from position values and derives propagated
  velocity from its derivative. The original velocity-equality criterion
  therefore tested a guarantee GMAT does not make. Its observed FAIL and
  raw residuals stay intact; the result neither approves nor disproves ICRF
  frame compatibility. [Decision 0004](decisions/0004-gmat-stk-position-transfer-gate.md)
  freezes a direct-reference continuous-time position gate and a 1 s versus
  0.5 s position-convergence gate before new results. The documented
  semantics do not, by themselves, quantitatively explain every velocity
  residual. This is a validation-method discrepancy, not a production defect.
- **Corrected disposition:** The predeclared 13-point direct-reference
  position gate passed (maximum `7.17963611987e-6 km`, limit `0.001 km`),
  and the 1 s versus 0.5 s GMAT position-convergence gate passed (maximum
  `1.63010147317e-6 km`, limit `0.0001 km`). ICRF was therefore approved
  for the bounded Phase A ContactLocator run; the historical sample gate
  remains FAILED. Phase A found one corresponding event per station and
  passed the frozen 0.25 s AOS/LOS, 0.50 s duration and 0.02 s transfer
  event-shift criteria. See [corrected transfer evidence](../validation/gmat/icrf/corrected_position/README.md)
  and [Phase A report](../validation/gmat/phase_a/README.md). This does not
  resolve the Fixed import's internal mechanism or provide physical orbit
  accuracy or independent SGP4 evidence.
