# Verification evidence — M1a

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
