# Spacecraft Mission Analysis Tool

A reproducible spacecraft mission-analysis demonstrator for archived TLE
propagation, coordinate-frame handling, ground-station visibility, access
windows, and temporal station coverage. **The TLE → SGP4 → TEME orbit kernel
and TEME → ITRS frame conversion exist today.** This is a portfolio engineering
project, not operational mission software.

## Status and scope

- M0: the orbit-kernel design and verification case are agreed; acceptance
  criteria for later geometry and events remain to be defined.
- M1a: archived TLE → WGS72 SGP4 → typed TEME state is implemented and verified.
- M1b: TEME → ITRS is implemented and passes a matched split-UT1 independent
  reference at the original 10 mm position and 0.1 mm/s velocity limits. The
  printed Appendix C position retains a documented 3.17 mm limit overrun
  because its reproducible single-JD path has a different numerical UT1 instant.
- Station geometry, access events, temporal coverage, versioned outputs, and
  independent end-to-end validation have not started.

The planned baseline is one spacecraft per analysis, archived TLEs, fixed
ground stations, geometric visibility, and temporal station coverage. Eclipse,
geographic sensor coverage, live TLE fetching, and operational scheduling are
outside the current baseline. See [requirements](docs/requirements.md) and
[architecture](docs/architecture.md) for status by component.

## Current orbit-kernel contract

`TleRecord.from_lines(line1, line2, source=...)` preserves exact checksum-bearing
69-character lines, validates their structure, and records the catalogue ID
and UTC epoch. `Sgp4Propagator(tle).propagate(time)` requires a scalar UTC
Astropy `Time`, explicitly selects WGS72, and passes `time.jd1` and `time.jd2`
separately to SGP4. It returns a `TemeState` with TEME position in **km** and
velocity in **km/s**. A nonzero SGP4 status raises `PropagationError` with its
code and message; it cannot return a valid-looking state after failure.

TLEs contain SGP4-compatible mean elements, not ordinary osculating Keplerian
elements. The [python-sgp4 documentation](https://github.com/brandon-rhodes/python-sgp4)
describes the model and output convention; the
[Astropy satellite guide](https://docs.astropy.org/en/stable/coordinates/satellites.html)
shows the split-Julian-date call.

## Install and verify

Python **3.11 or newer** is required. Direct dependencies and developer tools
are pinned in `pyproject.toml`. On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
```

After installation, the tests use archived local data and require no network
access. The Vanguard 1 / catalogue 00005 **+360 minute** reference case
reproduces the full printed vector from `python-sgp4==2.27` with maximum
component residuals of `4.293e-9 km` and `3.737e-10 km/s` against fixed limits
of `2e-7 km` and `2e-9 km/s`. See [verification](docs/verification.md) and
[fixture provenance](tests/fixtures/sgp4/README.md). This is same-model
software verification, not evidence of physical orbit accuracy.

## Repository guide

- `src/spacecraft_mission_analysis/`: implemented orbit kernel and frame conversion.
- `tests/`: contract, failure-path, and reference-vector tests; `fixtures/`
  holds the minimal archived verification case.
- `docs/`: requirements, assumptions, architecture, verification, validation
  status, issue log, and decision-record convention.
- `examples/`: intended home for reviewed worked cases; none exist yet.
- `.github/workflows/ci.yml`: checks the package on push and pull request.

## Engineering limits

The software is **not flight-qualified** and **not operational mission
software**. TLE predictions depend on the SGP4 model and TLE age. The current
reference-vector check confirms integration with the same/reference model
family; the matched frame comparison checks the M1b transformation at one
controlled case. Neither establishes physical orbit truth, ground-station
access, or end-to-end validation. See
[validation](docs/validation.md) for the evidence still needed.
