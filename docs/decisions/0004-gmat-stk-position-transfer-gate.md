# 0004 — GMAT STK transfer qualification by continuous-time position

Date: 2026-10-23. Status at freeze: corrected gate pending. Affected
requirement: MA-07. This record supersedes the *method* in Decision 0003,
not its historical failed result or raw evidence.

Execution disposition: **both corrected position gates passed** at all 13
predeclared epochs. Maximum 1 s GMAT-versus-direct-production position
difference was `7.17963611987e-6 km` against `0.001 km`; maximum GMAT 1 s
versus 0.5 s position difference was `1.63010147317e-6 km` against
`0.0001 km`. The ICRF transfer is approved for the bounded Phase A
ContactLocator comparison. The [full per-epoch vectors and residuals](../../validation/gmat/icrf/corrected_position/README.md)
are retained. The original Decision 0003 sample gate remains FAILED.
The subsequent [Phase A event comparison](../../validation/gmat/phase_a/README.md)
passed its unchanged count/order, 0.25 s AOS/LOS, 0.50 s duration and
0.02 s transfer event-shift criteria. Phase B remains outside this bounded
execution.

## Question and evidence

Decision 0003 provisionally required GMAT STK propagation to reproduce both
serialized ICRF position and supplied TimePosVel velocity at exact file nodes.
The Astropy-versus-Skyfield inertial conversion passed, and GMAT
`GetEphemStates(..., EarthICRF)` reproduced file endpoints. The propagated
sample gate failed: velocity residuals were `0.001141886`, `0.000448212`
and `0.000401191 km/s`; position residuals at 20:20 and 20:40 were about
2 mm against a 1 mm limit. These measurements and the FAIL remain retained.

The installed GMAT R2026a `Propagator.html` STK Implementation Notes say
default position interpolation is a seventh-order Hermite-Newton divided
difference polynomial using position samples only, and the propagated
velocity comes from its derivative. On the long, unsegmented ephemeris used
here, the supplied velocity column is not an equality contract for
propagated velocity. This establishes a mismatch between the initial
velocity criterion and documented implementation semantics. It does not
quantitatively explain every observed velocity residual, nor establish a
production defect or prove the ICRF frame transfer valid.

## Corrected choice and alternatives

The purpose is event-location comparison, for which continuous-time
trajectory position is the relevant transfer quantity. Qualify the existing
1 s ICRF transfer against a *direct* production SGP4→TEME→validation-only
GCRS position at predeclared nodes, midpoints and fractional times. Require
the maximum Euclidean position difference ≤1 m. Also compare GMAT positions
from 1 s and 0.5 s transfer files at the same times, requiring ≤0.1 m.
The [frozen protocol](../../validation/gmat/icrf/corrected_position/PROTOCOL.md)
defines exact epochs, conventions, stop conditions and rationale before
results. Keep velocity differences as diagnostics only.

Keeping the old velocity rule would test a guarantee GMAT does not make.
Trying another frame or tuning interpolation settings is outside this
controlled hypothesis. No acceptance threshold is selected from observed
corrected-gate residuals.

## Consequences and verification impact

The initial ICRF sample gate stays **failed under its frozen criteria**.
ICRF approval remains pending both corrected position gates. A pass would
qualify only the numerical transfer for Phase A, not orbit truth or event
agreement. The original event limits and 1 s versus 0.5 s **event-shift**
limit remain separate and unchanged. Production code, evidence, numerical
models and MA-07 status do not change.
