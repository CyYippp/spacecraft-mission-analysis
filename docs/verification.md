# Verification evidence — M1a and M1b

**Verification** asks whether the specified TLE-to-TEME software boundary was
built correctly. **Validation** asks whether the eventual mission-analysis
model is useful for the intended planning question; see [validation](validation.md).

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

## M1b published frame comparison

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

Calculated minus published components with the printed inputs are:

- Position: `(-1.317365741e-5, -1.729577889e-6, -4.887897376e-8)` km.
- Velocity: `(+7.095414922e-8, +3.933593007e-9, +3.025828477e-10)` km/s.

**The first position component exceeds its frozen 10 mm limit by 3.17 mm.**
The other position components and all velocity components meet their limits.
The strict expected-failure test preserves this discrepancy visibly in CI;
it is not a passing position acceptance. The printed input and limit were not
changed. Investigation confirmed the specified UTC/EOP values and Astropy's
Vallado-compatible GMST82 and polar-motion path. A diagnostic 20 µs time
shift moved that component by 11.52 mm, indicating sensitivity at this scale;
the root cause of the paper/Astropy difference remains unresolved.

The velocity comparison independently remains an active passing test. Simply
rotating the velocity, without accounting for Earth rotation, would miss by
roughly `ω⊕ × r` (about 0.58 km/s at this radius), far above `1e-7 km/s`.
The tests also check the typed state, exact split time, three finite components,
scoped IERS restoration, and an out-of-range EOP error before state return.
