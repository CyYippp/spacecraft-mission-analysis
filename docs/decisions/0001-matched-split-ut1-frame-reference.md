# 0001 — Matched split-UT1 reference for M1b frame verification

Date: 2026-10-15. Status: approved by the project owner. Affected requirements:
MA-03 and MA-07. Scope: the Appendix C TEME→ITRS verification case only.

## Previous decision

Use Vallado Appendix C's printed ITRF vector directly as the acceptance oracle
for the production split-UT1 transform, with per-component limits of `1e-5 km`
for position and `1e-7 km/s` for velocity. Its x-position residual exceeded the
position limit by 3.17 mm and was retained as a strict expected failure.

## Reason for change

The reproducible published-reference calculation first rounds UTC into one
IEEE-754 Julian date and then applies DUT1. The production calculation preserves
split UT1. These evaluation paths have numerically different UT1 instants at
the case epoch, so the printed vector is not a matched-epoch acceptance oracle
at the frozen 10 mm limit.

## Evidence and alternatives

The single-JD path reproduces the printed vector within the reference check.
It differs from split UT1 by `+22.789995 µs` and `+1.661869753e-9 rad` of
GMST phase. At matched split UT1, independent Vallado/Skyfield GMST82 and
Astropy/PyERFA agree within `2.664535259e-15 rad`; corresponding rotation
matrices agree within `1.998401444e-15` per element. See the
[verification record](../verification.md) for vectors and residuals. The exact
arithmetic used to produce Vallado's original printed vector is unavailable;
the single-JD reproduction is a strongly supported numerical explanation.

Retaining the printed vector as the direct oracle would require accepting a
known numerical epoch mismatch. Relaxing the position limit or degrading
production precision would hide the discrepancy. Neither is adopted.

## New decision

Keep the printed-vector comparison as a separate **published-reference
reproduction** test using the historical single-JD path. Use independent
verification-only Vallado equations evaluated with the same split UT1, DUT1,
polar motion, and physical epoch as production for **production acceptance**.
Keep the original `1e-5 km` and `1e-7 km/s` per-component limits unchanged.

## Impact on requirements and tests

MA-03 frame conversion now has active matched split-UT1 position and velocity
acceptance tests. MA-07 gains this bounded independent frame comparison; later
station geometry and end-to-end or GMAT comparisons remain unverified. The
original production-minus-printed discrepancy remains in the evidence record.
The strict expected failure is removed only after the replacement tests pass.
No production `frames.py` code or engineering model baseline changes.
