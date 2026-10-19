# Spacecraft Mission Analysis Tool

A portfolio mission-analysis demonstrator for archived-TLE propagation and
fixed-station geometric access. It traces a spacecraft state through coordinate
frames to station viewing geometry and threshold-crossing windows. It is not
operational or flight-qualified mission software.

## Current scope and status

The implemented path is:

```text
archived TLE → WGS72 SGP4 → TEME → ITRS → station-relative ITRS
             → ENU → geometric azimuth/elevation/range
             → elevation threshold → access entry/exit, duration and peak
```

The orbit, frame, station, look-angle and access boundaries have component
verification. The frozen Skyfield Phase B hold-out **passed its downstream
numerical agreement criteria** under matched Earth orientation, with a shared
SGP4 kernel. This does not independently validate propagation or establish
physical pass-time accuracy. See the [live requirements](docs/requirements.md)
for the disposition of each MA requirement.

The planned scope is one spacecraft per analysis, archived TLEs, fixed WGS84
stations, geometric visibility and eventual temporal station coverage.
Versioned product CSV/JSON, TLE-age and unsupported-interval warnings,
independent propagation/GMAT comparison, and temporal coverage remain open or
not started. Peak elevation is analytically verified and checked on an internal
archived-orbit case; it has no separate independent comparison. Live TLE
fetching, eclipse, geographic sensor coverage and operational scheduling are
outside the baseline.

## Run and verify

Python 3.11 or newer is required. Dependencies and developer tools are pinned
in [pyproject.toml](pyproject.toml). There is no CLI or product-output layer yet;
the [Python API](src/spacecraft_mission_analysis/__init__.py) is exercised by
the local [tests](tests/) and [validation code](tests/validation/).

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev,validation]'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q
```

The tests use archived local data and require no network access. The reference
case is Vanguard 1, catalogue 00005, propagated **+360 minutes** from its
archived TLE epoch. The fixed `python-sgp4==2.27` fixture gives TEME position
`(-7154.03120202, -3783.17682504, -3536.19412294) km` and velocity
`(4.741887409, -4.151817765, -2.093935425) km/s`. The adapter uses scalar
UTC Astropy `Time`, split `jd1`/`jd2`, and explicit SGP4 errors. See the
[fixture provenance](tests/fixtures/sgp4/README.md) and
[verification record](docs/verification.md) for fixed limits and residuals.

## Evidence and authority

The external portfolio plan `01-spacecraft-mission-analysis.md` remains the
scope and intent baseline. **This repository is the source of truth for current
implementation state.** Its records have separate jobs:

- [Requirements](docs/requirements.md): live MA-01–MA-08 status and traceability.
- [Assumptions](docs/assumptions.md): modelling conventions and boundaries.
- [Architecture](docs/architecture.md): implemented interfaces and data path.
- [Verification](docs/verification.md): specified software behaviour, fixtures,
  criteria and results.
- [Validation](docs/validation.md): cross-implementation evidence, frozen
  hold-out, independence limits and disposition.
- [Issues](docs/issues.md): concise discrepancy and limitation register.
- [Decisions](docs/decisions/README.md): approved engineering baseline choices.
- [Learning/fault log](docs/engineering-learning-and-fault-log.md): educational
  and historical companion, subordinate to the records above.
- [Changelog](CHANGELOG.md): chronological repository changes.

The direct Vallado Appendix C printed-vector x-position comparison retains a
documented **3.17 mm overrun** of its frozen position limit. Decision 0001
established a matched split-UT1 reference for active frame acceptance without
loosening that limit. The 5 s access sampling grid can miss narrow near-grazing
intervals, and a peak hidden between samples cannot be certified as the global
maximum; Skyfield shares the installed SGP4 kernel. These limits and their
dispositions remain visible in the [issue register](docs/issues.md).
