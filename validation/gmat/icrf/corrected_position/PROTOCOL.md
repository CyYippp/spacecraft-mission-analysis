# Corrected GMAT STK ICRF position-transfer gate — frozen protocol

Frozen 2026-10-23 before running any corrected continuous-time comparison or
generating the 0.5 s STK file. The previous ICRF exact-grid position-and-
velocity gate remains formally **failed** under its original limits; its
reports and result are retained in `../`. The installed GMAT R2026a
`Propagator.html` STK Implementation Notes state that default position
interpolation is seventh-order Hermite-Newton divided difference from
position data only, and reported velocity is the derivative of the position
polynomial. The supplied TimePosVel velocity column is therefore not an
equality oracle for propagated GMAT velocity on this long segment. Velocity
remains a diagnostic, without a PASS/FAIL criterion.

## Fixed diagnostic times and direct reference

All times are UTC on 2000-06-27, from the canonical archived Vanguard input.
Use these exact epochs, in this order:

1. 20:00:00.000 (1 s and 0.5 s nodes)
2. 20:00:00.500 (1 s midpoint, 0.5 s node)
3. 20:03:17.123 (non-half-second)
4. 20:10:00.000 (nodes)
5. 20:10:00.500 (midpoint)
6. 20:17:43.371 (non-half-second)
7. 20:20:00.000 (nodes)
8. 20:20:00.500 (midpoint)
9. 20:30:00.000 (nodes)
10. 20:30:00.500 (midpoint)
11. 20:33:08.777 (non-half-second)
12. 20:39:59.500 (midpoint)
13. 20:40:00.000 (nodes)

At each time, directly propagate the archived TLE with production WGS72 SGP4
using split Julian dates, then transform the resulting TEME Cartesian state
with validation-only Astropy `TEME(obstime=t)→GCRS(obstime=t)`. Scope the
canonical explicit test EOP snapshot with network download disabled. Do not
interpolate STK samples to obtain the reference. The GCRS-to-STK ICRF mapping
remains the provisional geocentric ICRS-aligned transfer convention from
Decision 0003.

## Position gates

First, compare GMAT STK-propagated `EarthICRF` position from the **existing**
1.0 s file against the direct production reference at every listed time.
Require `max Euclidean position residual ≤0.001 km` (1 m). This is a
validation-transfer fidelity limit, not orbital physical accuracy. A 1 m
along-track difference at characteristic spacecraft speeds of km/s has a
timing scale far below the frozen Phase A 0.25 s event limit. Do not adjust
the limit after exposure.

Generate a separate 0.5 s Earth-centered STK ICRF TimePosVel file over the
same padded 19:59:00–20:41:00 span, with the same TLE, WGS72, explicit EOP
snapshot, TEME→GCRS convention, units, and high-precision serialization.
Preserve generator, file, SHA-256 and metadata. At the **same 13 epochs**,
compare GMAT STK-propagated positions from the 1.0 s and 0.5 s files. Require
`max Euclidean position difference ≤0.0001 km` (0.1 m). This is the
interpolation-convergence limit, distinct from the future event-shift check.

GMAT reported velocity and direct production inertial velocity may be
recorded as diagnostic-only values. No velocity acceptance limit applies.
GMAT UTC epoch labels must equal the requested timestamps. Any failed
position gate or timing label stops work for engineering review, with raw
evidence retained. No other transfer frame or interpolation setting is
trialled. Only if both position gates pass may the previously frozen Phase A
ContactLocator comparison proceed, retaining its original event count/order,
AOS/LOS ≤0.25 s, duration ≤0.50 s, ContactLocator StepSize 1 s,
disabled light-time and stellar aberration, and 1.0-versus-0.5 s event shift
≤0.02 s. ContactLocator Earth shape/orientation configuration must be
recorded because it is SPICE-based and separate from core propagation.
