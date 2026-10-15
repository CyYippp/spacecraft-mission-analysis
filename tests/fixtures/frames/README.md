# Vallado Appendix C frame fixture

The machine-readable case is transcribed from **Vallado et al., _Revisiting
Spacetrack Report #3_, AIAA 2006-6753 Rev. 2, Appendix C, printed page 32**:
[authoritative PDF](https://celestrak.org/publications/AIAA/2006-6753/AIAA-2006-6753-Rev2.pdf).
It is independent of the `python-sgp4` orbit-vector fixture. The paper calls
the output ECEF (ITRF). Astropy's Earth-fixed `ITRS` is compared with that
published ITRF vector at the same UTC epoch and Earth-orientation inputs.

- Epoch: `2004-04-06T07:51:28.386` UTC; published `ΔAT=32 s`.
- EOP at that instant: `UT1−UTC=−0.439961 s`, `xp=−0.140682 arcsec`,
  `yp=+0.333309 arcsec`.
- TEME position: `(5094.18016210, 6127.64465950, 6380.34453270)` km.
- TEME velocity: `(−4.746131487, 0.785818041, 5.531931288)` km/s.
- Published ITRF position: `(−1033.47938300, 7901.29527540,
  6380.35659580)` km.
- Published ITRF velocity: `(−3.225636520, −2.872451450,
  5.531924446)` km/s.

The production acceptance test builds a two-day **test-only** Astropy IERS table
with constant published EOP values across the case epoch. This makes Astropy's interpolation
at the instant equal the published inputs; it does not claim those constants
describe the surrounding days. Automatic IERS download is disabled only in
the scoped test context, which restores the previous settings afterwards.

## Frozen acceptance criteria

The test limits were declared before evaluating the Astropy result:

- Position: **`1e-5 km` per component** (1 cm).
- Velocity: **`1e-7 km/s` per component** (0.1 mm/s).

The paper prints position to `1e-8 km`, velocity to `1e-9 km/s`, UT1−UTC to
`1e-6 s`, and polar motion to `1e-6 arcsec`. Half a microsecond of UT1
rounding can move an approximately 8,000 km state by about 0.5 mm through
Earth rotation. The chosen limits allow decimal input precision and small
standards/library numerical differences while remaining far below the error
from omitting Earth rotation in velocity. They are not derived from a measured
residual. A failure requires investigation, not an adjusted limit.

## Direct printed-vector discrepancy and disposition

With Astropy 7.2.1 and the exact printed UTC/EOP inputs above, the calculated
minus published residuals are:

- Position: `(-1.317365741e-5, -1.729577889e-6, -4.887897376e-8)` km.
- Velocity: `(+7.095414922e-8, +3.933593007e-9, +3.025828477e-10)` km/s.

The first position component is **13.17 mm**, above the frozen 10 mm limit.
The other position components and all velocity components meet their limits.
This direct comparison remains recorded as evidence. The published numbers are
unaltered. The printed vector is reproduced by a separate single-JD reference
test, while active production acceptance compares an independent Vallado
calculation at matched split UT1 against the original 10 mm/0.1 mm/s limits.
See [decision 0001](../../../docs/decisions/0001-matched-split-ut1-frame-reference.md).

The [precision diagnosis](../../../docs/verification.md#published-reference-reproduction-and-single-jd-diagnosis)
reproduces the published position within Skyfield's `5e-8 km` reference check
by following its historical **single-JD** Appendix C path. Using the same
equations with Astropy's **split UT1 JD** instead reproduces Astropy's result.
The single-JD path is 22.79 µs later in Earth-rotation phase at this epoch;
that shift accounts for essentially the entire 13.17 mm x discrepancy. This
strongly bounds the numerical cause, but does not prove the exact arithmetic
used to generate Vallado's original printed vector. The matched split-UT1
production-minus-reference residuals are `(+2.137312549e-11,
+4.547473509e-12, 0) km` and `(-1.418474227e-10, -1.693534202e-11,
-1.170619157e-12) km/s`, within the unchanged limits. Full details are in the
[verification record](../../../docs/verification.md#active-matched-split-ut1-production-acceptance).
