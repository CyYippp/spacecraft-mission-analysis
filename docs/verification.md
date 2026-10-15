# Verification evidence — M1a and M1b

**Verification** asks whether the specified TLE-to-TEME and TEME-to-ITRS
software boundaries were built correctly. **Validation** asks whether the
eventual mission-analysis model is useful for the intended planning question;
see [validation](validation.md).

## Reference vector

The test uses Vanguard 1 / catalogue **00005** at **+360 minutes** after the
archived TLE epoch. Exact TLE lines, complete printed reference values, source
URLs, and source-file SHA-256 hashes are recorded with the
[fixture](../tests/fixtures/sgp4/README.md). Source files are from
`python-sgp4==2.27`: `SGP4-VER.TLE` and `tcppver.out`, derived from the Vallado
verification suite. The test builds a scalar UTC Astropy `Time` from split JD
parts and calls the public adapter.

Expected TEME position: `(-7154.03120202, -3783.17682504,
-3536.19412294)` km. Expected TEME velocity: `(4.741887409,
-4.151817765, -2.093935425)` km/s. **Predeclared per-component limits in
`tests/test_orbit.py`: `2e-7 km` position and `2e-9 km/s` velocity.** These
allow reference-file decimal printing and small C++/Julian-date-path numerical
differences; they were fixed before observing the adapter residuals.

Observed computed-minus-reference components with `sgp4==2.27` and
`astropy==7.2.1`:

- Position: `(+4.292814992e-9, +3.431978257e-9, -2.215529094e-9)` km;
  maximum absolute component `4.293e-9 km`.
- Velocity: `(-3.844036200e-12, -3.736939647e-10,
  +9.263390055e-11)` km/s; maximum absolute component `3.737e-10 km/s`.

## Contract and failure checks

The tests also check TEME typing, three finite components, exact input-line
preservation, immutable time exposure, catalogue/epoch metadata, malformed
TLE rejection, rejection of naive datetime/non-UTC/non-scalar inputs, and an
injected SGP4 code-6 failure. That failure raises `PropagationError` with the
code and package message; no state reaches the caller.

Run locally after installing `.[dev]`:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
```

The GitHub workflow runs these same checks on push and pull request with
Python 3.11. Passing this same-model vector test does not establish physical
orbit truth or validate future access outputs.

## M1b frame case and frozen limits

The independent fixture is [Vallado et al., _Revisiting Spacetrack Report #3_,
AIAA 2006-6753 Rev. 2, Appendix C, printed page 32](../tests/fixtures/frames/README.md).
At `2004-04-06T07:51:28.386` UTC it specifies `UT1−UTC = −0.439961 s`,
`xp = −0.140682 arcsec`, `yp = +0.333309 arcsec`, and `ΔAT = 32 s`.
The published TEME input is `(5094.18016210, 6127.64465950,
6380.34453270)` km and `(−4.746131487, 0.785818041, 5.531931288)` km/s.
The expected Earth-fixed ITRF result is `(−1033.47938300, 7901.29527540,
6380.35659580)` km and `(−3.225636520, −2.872451450,
5.531924446)` km/s. Astropy's corresponding Earth-fixed frame is ITRS.

The comparison uses a test-only two-day IERS table whose values are held at
the published EOP inputs around the case instant. This ensures interpolation
returns the printed values at that instant; the table is not a model of those
surrounding days. The test scopes `auto_download=False` and restores the
previous IERS table and configuration. Normal analysis leaves Astropy's
automatic download setting enabled. Installed versions for this local run:
`astropy==7.2.1`, `astropy-iers-data==0.2026.10.5.1.0.7`. No dependency pin
or version changed for M1b.

Before the comparison was run, the [fixture record](../tests/fixtures/frames/README.md)
froze per-component limits of `1e-5 km` (10 mm) for position and `1e-7 km/s`
(0.1 mm/s) for velocity. The paper prints position to `1e-8 km`, velocity to
`1e-9 km/s`, UT1 to `1e-6 s`, and polar motion to `1e-6 arcsec`. The limits
allow printed input precision and modest numerical convention differences;
they also detect an omitted Earth-rotation term in velocity by a large margin.

Production split-UT1 minus published components with the printed inputs are:

- Position: `(-1.317365741e-5, -1.729577889e-6, -4.887897376e-8)` km.
- Velocity: `(+7.095414922e-8, +3.933593007e-9, +3.025828477e-10)` km/s.

**The first position component exceeds its frozen 10 mm limit by 3.17 mm.**
The other position components and all velocity components meet their limits.
This remains a documented **direct printed-vector discrepancy**, not a passing
direct comparison. The printed input and limit were not changed. The
[approved decision](decisions/0001-matched-split-ut1-frame-reference.md)
retains the printed vector as historical reproduction evidence and defines the
active production oracle as independent Vallado equations at matched split
UT1. Investigation confirmed the specified UTC/EOP values and Astropy's
Vallado-compatible GMST82 and polar-motion path. A diagnostic 20 µs time
shift moved that component by 11.52 mm, indicating sensitivity at this scale.
The controlled precision diagnosis below explains the comparison offset.

The matched-reference velocity comparison is an active passing test. Simply
rotating the velocity, without accounting for Earth rotation, would miss by
roughly `ω⊕ × r` (about 0.58 km/s at this radius), far above `1e-7 km/s`.
The tests also check the typed state, exact split time, three finite components,
scoped IERS restoration, and an out-of-range EOP error before state return.

## Published-reference reproduction and single-JD diagnosis

The independent verification-only code in `tests/verification/vallado.py`
reproduces the equations and evaluation order in
[Skyfield's Appendix C test](https://github.com/skyfielders/python-skyfield/blob/31a6ed7584cd09b6e48e07546a4b5921e1cd5bb4/skyfield/tests/test_earth_satellites.py),
[GMST/TEME implementation](https://github.com/skyfielders/python-skyfield/blob/31a6ed7584cd09b6e48e07546a4b5921e1cd5bb4/skyfield/sgp4lib.py),
and [Julian-date builder](https://github.com/skyfielders/python-skyfield/blob/31a6ed7584cd09b6e48e07546a4b5921e1cd5bb4/skyfield/timelib.py).
It uses no Skyfield package at runtime. The following values were calculated
with the fixture's printed UTC and EOP inputs under the scoped IERS table.

- Fresh UTC split JD: `(2453102.0, -0.17258812500000004)`.
- Astropy retrieves `UT1−UTC = -0.439961 s`, `xp = -0.140682 arcsec`, and
  `yp = +0.333309 arcsec` (all table statuses `0`). The resulting split UT1
  JD is `(2453102.0, -0.17259321714120376)`.
- `erfa.gmst82(ut1.jd1, ut1.jd2) = 5.4595625860266885 rad`. Skyfield's
  Appendix C GMST1982 equation with that **same split UT1 instant** yields
  `5.459562586026686 rad`, a difference of `-2.664535259e-15 rad` or
  `-0.00003654 µs` of sidereal phase.
- Skyfield's published test builds one floating-point `jd_utc`, then adds
  DUT1 as `jd_utc + dut1/86400`. This gives `2453101.827406783` UT1 JD and
  `5.459562587688558 rad`. Relative to split UT1, it is `+22.789995 µs` in
  time and `+1.661869753e-9 rad` (`+0.000342785 arcsec`) in GMST phase.
  One float64 JD unit in the last place here is `40.233135 µs`. Simply
  collapsing Astropy's split UT1 with `jd1 + jd2` produces a *different*
  `-17.443141 µs` error; evaluation order matters.

The Astropy/PyERFA matrix and the Skyfield-equation matrix using split UT1
agree element by element. Their maximum absolute element difference is
`1.998401444e-15`; the full Astropy-minus-Skyfield-split residual matrix is:

```text
[[+1.998401444e-15, +1.776356839e-15, 0],
 [-1.776356839e-15, +1.998401444e-15, 0],
 [-1.694065895e-21, +4.446922973e-21, 0]]
```

Replacing only the split GMST input with the single-JD value changes the
Astropy-minus-Skyfield matrix to:

```text
[[-1.219168433e-9, -1.129353500e-9, 0],
 [+1.129353500e-9, -1.219168433e-9, 0],
 [+9.934250163e-16, -2.740358578e-15, 0]]
```

The PEF position is `(-1033.4750444880924, 7901.3055838546325,
6380.3445327)` km using split UT1 and `(-1033.475031357152,
7901.305585572133, 6380.3445327)` km using single-JD UT1. After polar
motion, the single-JD calculation gives the following calculated-minus-
published residuals:

- Position: `(-4.271714715e-8, -1.207899913e-8, -4.886715033e-8)` km,
  inside Skyfield's own `5e-8 km` check.
- Velocity: `(+6.632236316e-8, +9.311117655e-9, +3.037587959e-10)` km/s,
  inside Skyfield's own `7e-8 km/s` check.

With `xp = yp = 0`, the split-vs-single xy position difference persists as
`(+1.313094049e-5, +1.717500709e-6)` km, ruling out polar motion as its
dominant source. The difference between the split and single results almost
exactly cancels the original position residual.

Time caching was tested separately. A fresh `Time` made inside the IERS
context and an untouched `Time` made before it both use the published DUT1 and
give the same position. A `Time` whose UT1 was accessed *before* entering the
context retains `-0.440425036040625 s` DUT1 and gives x position
`-1033.4796635384494 km`, far from the observed residual. The public adapter
reconstructs a fresh `Time` from the immutable split JD and still returns
`-1033.4793961736575 km` even when the source `Time` had a cached UT1.
Caching is therefore not the cause in this test, although direct reuse of
Astropy `Time` after changing IERS context can matter elsewhere.

**Disposition:** the discrepancy is strongly bounded to the published
single-JD numerical path. Skyfield's reproducible calculation shows how the
printed vector arises, but the original author's internal arithmetic is not
available to prove its exact historical path. The historical reproduction test
uses Skyfield's `5e-8 km` and `7e-8 km/s` checks for the printed vector. This
test does not accept the production implementation.

## Active matched split-UT1 production acceptance

The independent function in `tests/verification/vallado.py` evaluates GMST1982,
the TEME→PEF rotation, the Earth-rotation velocity term, and the polar-motion
rotations using ordinary numerical operations. It does not call production
`teme_to_itrs()` or Astropy's high-level frame transformation. The test supplies
the same published TEME vector and xp/yp to this function. Its split UT1 comes
from the fixture's UTC epoch and exact DUT1 under the scoped IERS table; the
production calculation runs under that same table. The test compares the two
results directly at the **unchanged** per-component `1e-5 km` position and
`1e-7 km/s` velocity limits.

Production minus independent matched split-UT1 components with Astropy 7.2.1:

- Position: `(+2.137312549e-11, +4.547473509e-12, 0)` km; maximum absolute
  component `2.138e-11 km`.
- Velocity: `(-1.418474227e-10, -1.693534202e-11, -1.170619157e-12)`
  km/s; maximum absolute component `1.419e-10 km/s`.

Both active position and velocity acceptance tests pass. No acceptance-related
expected failure remains. The production frame code and original 10 mm limit
are unchanged. This is a controlled single-case software comparison, not a
claim of general physical or end-to-end mission-analysis validity.
