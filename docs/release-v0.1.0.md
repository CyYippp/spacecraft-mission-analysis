# v0.1.0 — bounded spacecraft access demonstrator

## Purpose and bounded use

This portfolio analysis demonstrator takes one archived TLE, one or more fixed
stations and a finite UTC interval. It reports geometric access windows and
temporal coverage for that configured case. It is not an operational pass
prediction, navigation, or physical orbit-truth product.

The first release follows the formal MA-01–MA-08 access/temporal-coverage path;
the planning baseline prioritizes releasing that path first. Standalone state
history, ground-track products and product plotting are deferred because they
are unnecessary to close these requirements and would add implementation and
verification scope. No such product is claimed here.

## Architecture

`archived input → WGS72 SGP4/TEME → time/frame service → WGS84 station geometry → access events → temporal coverage → JSON/CSV`

See [architecture](architecture.md), [input contract](input-schema-v1.md), and
[run/output contract](run-schema-v1.md). The installed command invokes these
same input and run interfaces.

## Worked Vanguard case

The committed [Vanguard run](../examples/vanguard_run/) uses catalogue 00005,
the Vallado/python-sgp4 verification TLE, 2000-06-27 20:00–20:40 UTC, a 10°
mask, and synthetic fixed WGS84 stations at 0°N 0°E and 1°N 1°E. Its
`test_only_eop.json` is an explicit, hashed, config-relative **test-only** zero
UT1−UTC/polar-motion fixture; it is not a physical Earth-orientation claim.

| Station | Detected 10° window UTC | Duration |
| --- | --- | ---: |
| Equator Greenwich | 20:11:00.831787810–20:31:30.099808909 | 1229.2680210995704 s |
| 1N 1E | 20:12:13.258505293–20:30:57.478295163 | 1124.2197898697889 s |

The union has one interval, **1229.2680210995704 s** access,
**0.5121950087914875** coverage fraction and **660.8317878096642 s** longest
no-access gap. These are copied from the archived [run.json](../examples/vanguard_run/run.json),
not new measurements.

## Requirement disposition

| Requirement | Status | Evidence |
| --- | --- | --- |
| MA-01 archived input | VERIFIED | Exact TLE and source preservation, strict loader |
| MA-02 SGP4 propagation | VERIFIED | Reference vector, signed epoch offset, explicit failure |
| MA-03 frames/geometry | PARTIALLY VALIDATED | Matched split-UT1 equations, station/ENU fixtures, bounded comparison |
| MA-04 access events | PARTIALLY VALIDATED | Analytic roots/peaks, archived run, bounded event comparison |
| MA-05 outputs/provenance | VERIFIED | Schema 1.1, reproducible config/EOP, archived bundle |
| MA-06 warnings/failures | VERIFIED | Structured notices and fail-closed fault tests |
| MA-07 independent comparison | PARTIALLY VALIDATED | Skyfield and GMAT Phase A/B within stated boundaries |
| MA-08 temporal coverage | VERIFIED | Hand-calculated A–K cases and archived integration |

`PARTIALLY VALIDATED` records bounded evidence with known limitations; it is
not a failed release. The [live requirements](requirements.md) and
[verification](verification.md) give exact dispositions and numerical limits.

## Verification and validation highlights

- The [published SGP4 reference vector](verification.md#ma-02-sgp4-propagation)
  passes its fixed position/velocity limits. The typed TEME state reports signed
  SGP4 minutes since the TLE epoch; error codes cannot return a valid state.
- Independent [matched split-UT1 frame equations](verification.md#active-matched-split-ut1-production-acceptance)
  pass the original component limits. Analytic [access](verification.md#elevation-threshold-events)
  and [coverage](verification.md#ma-08-temporal-station-coverage) tests cover
  event and interval arithmetic.
- The frozen [Skyfield Phase B hold-out](validation.md#phase-b-first-observed-hold-out-result--pass)
  passes downstream numerical criteria while sharing `sgp4==2.27`.
- [GMAT Phase A](validation.md#gmat-r2026a-same-trajectory-event-comparison--phase-a-pass)
  passes cross-tool event location on an imported production trajectory: maximum
  AOS/LOS residual 0.050494707 s versus 0.25 s and duration residual
  0.050373770 s versus 0.50 s. [Phase B](validation.md#gmat-independent-numerical-propagation-diagnostic--phase-b)
  passes initial-state transfer and numerical repeatability gates under
  deliberately different dynamics; its cross-model divergence is diagnostic.

## Engineering discrepancy and provenance

The GMAT STK `Fixed` transfer gate failed. The first ICRF gate also failed:
its velocity equality criterion assumed a contract the installed STK
propagator documentation did not provide. Both failures and raw results remain
recorded. [Decision 0004](decisions/0004-gmat-stk-position-transfer-gate.md)
changed the *method* to predeclared continuous-time position fidelity, which
passed before Phase A event comparison passed. The original failed gate was
not relabelled or loosened to pass.

The GMAT records document criteria as frozen before execution and retain
protocols, raw results and failed attempts. Protocol and result files were
committed together, however, so Git history alone cannot independently
timestamp protocol freeze before result exposure. This is a provenance
limitation, not a validation failure.

## Limits and release decision

Inputs are archived TLEs; stale-TLE uncertainty is unquantified. A finite 5 s
event-discovery grid can miss narrow access, and the peak search cannot certify
against arbitrary hidden higher peaks. The Vanguard zero-EOP table is a
reproducibility fixture, not physical EOP. Skyfield shares the SGP4 kernel;
GMAT Phase A imports the production trajectory, while Phase B uses different
dynamics. Independent same-model SGP4 propagation accuracy and physical
pass-time accuracy remain open. The [issue register](issues.md) records these
boundaries.

**Release disposition:** v0.1.0 is credible as a reviewer-facing portfolio
demonstrator because every MA requirement has evidence and a stated
disposition, one archived case reproduces, and the validation boundaries are
explicit. It is not flight-qualified, certified, operational, or a physical
orbit-truth product.

## Clean-install reproduction

On Windows `Windows-10-10.0.26200-SP0`, a new external Python `3.11.9`
virtual environment received a **non-editable** `python -m pip install
"C:\Users\Cyrus\Documents\ChatGPT\P1 - Spacecraft Mission Analysis Tool"`
from committed candidate `5c8a8f353f178389f175f26ca3db217c8186b303`. Installed versions:
`spacecraft-mission-analysis==0.1.0`, `sgp4==2.27`, `astropy==7.2.1`,
`scipy==1.17.1`; `pip check` passed. The only later candidate amendment
records this rerun in documentation.

From outside the repository, the exact invocation was:

```powershell
& 'C:\Users\Cyrus\AppData\Local\Temp\p1-release-v010-bbc71657400344138c8d9ed6a340fc62\Scripts\spacecraft-mission-analysis.exe' 'C:\Users\Cyrus\Documents\ChatGPT\P1 - Spacecraft Mission Analysis Tool\examples\vanguard_run\config.json' --output-dir 'C:\Users\Cyrus\AppData\Local\Temp\p1-release-v010-bbc71657400344138c8d9ed6a340fc62\fresh-output'
```

Exit code **0**; the concise result was `SUCCESS`, two stations, two station
windows, one merged interval, coverage fraction `0.512195008791`, zero
warnings. Output membership was `run.json` plus `access_windows.csv`,
`coverage.csv`, `run.csv`, `stations.csv`, `union_intervals.csv` and
`warnings.csv` under `csv/`.

The [PR #10 comparison rule](../tests/test_input.py) checks all stable JSON
bytes and five CSV files exactly, checks access-window CSV nonpeak fields
exactly, and permits only optimizer peak time/elevation under their frozen
`0.02 s`/`1e-5 deg` limits. This rerun passed those rules: maximum peak-time
and elevation differences were both **zero**. An additional SHA-256 comparison
found **all seven generated files byte identical** to the archived bundle.
