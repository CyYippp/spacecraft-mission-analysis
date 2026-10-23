# 0003 — Provisional ICRF transfer for GMAT comparison

Date: 2026-10-23. Status at protocol freeze: **trial only; hard gates pending**. Affected
requirement: MA-07. No production baseline or acceptance criterion changes.

Execution disposition: the independent conversion and GMAT endpoint parser
gates passed, but the exact-grid propagated-sample gate **failed**. ICRF is
therefore **not approved** for Phase A ContactLocator use. See the retained
[trial results](../../validation/gmat/icrf/README.md). This outcome does not
alter the frozen pre-execution protocol below.

Subsequent [Decision 0004](0004-gmat-stk-position-transfer-gate.md) corrected
the validation method after installed GMAT documentation established its STK
interpolation semantics. Both newly frozen position gates passed and the
transfer was then approved for Phase A. This does not change the earlier
frozen sample-gate failure or its raw evidence.

## Question, context, and evidence

How should the production SGP4 trajectory be transferred to GMAT R2026a for
an event comparison? The prior validation proposal used STK `Fixed` to avoid
an extra inertial transformation. GMAT parsed the file, but its propagated
state differed from the intended Earth-fixed state by 0.734178219 km at
20:00 UTC. The difference is almost a one-sidereal-second Z rotation; tests
of time tags, TAI−UTC, ±1 s epoch shifts, direct EarthFixed input, and EOP
did not explain the inter-path residual. The precise internal mechanism is
unknown. The previous transfer method fails the predeclared same-state gate.
See the retained [diagnostic](../../validation/gmat/fixed_gate_diagnostic/README.md).

## Provisional choice and alternatives

Trial only STK `CoordinateSystem ICRF`, documented in the installed R2026a
STK ephemeris/propagator help and matched by GMAT `EarthICRF`. A
validation-only Astropy TEME→GCRS conversion maps geocentric ICRS-aligned
coordinates provisionally to the STK ICRF Earth-centered transfer. Its
frame-convention difference is explicit; independent Skyfield conversion
agreement and GMAT import/propagation gates must pass before ContactLocator.
The exact [frozen protocol](../../validation/gmat/icrf/PROTOCOL.md) precedes
any transfer result. J2000, TEMEOfDate, and other transfer methods are not
trialled here. They require a separate decision if ICRF fails.

## Consequences and verification impact

The trial adds a validation-only inertial conversion and an independent
conversion check. It does not add a production API or change TEME→ITRS,
Earth-orientation policy, previous artifacts, MA-07 status, or the Phase A
event limits. A failed gate leaves ICRF unapproved and requires engineering
review before another transfer method.
