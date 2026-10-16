# Validation status — Skyfield Phase A development characterization

The analytic access tests are **verification**, and the archived Vanguard 1
smoke test is **internal integration verification**. Phase A adds
**downstream cross-implementation validation with a shared SGP4 kernel**.
Skyfield 1.55 constructs its `EarthSatellite` through the same installed
`sgp4==2.27` package used by production. This is not independent SGP4
propagation, operational orbit prediction, or a frozen hold-out acceptance
test. Installed versions for this record: Skyfield 1.55, sgp4 2.27, Astropy
7.2.1, SciPy 1.17.1. Skyfield is a `validation` optional dependency only.

The reproducible [Phase A comparison code](../tests/validation/skyfield_phase_a.py)
and its [complete observed JSON report](../tests/validation/phase_a_results.json)
record every raw and refined event time, elevation and timing residual, clipped
interval, and pointwise near-crossing result. Run the comparison with
`python tests/validation/skyfield_phase_a.py`; CI installs `.[dev,validation]`.
Only the two fixed development cases below are in the executable registry.

## Shared inputs and controlled Earth orientation

Both paths use the exact [archived Vanguard 1 catalogue 00005 TLE](../tests/fixtures/access/vanguard_greenwich.json)
with its [Vallado/python-sgp4 provenance](../tests/fixtures/sgp4/README.md).
Skyfield parses catalogue 5. Its model's split SGP4 epoch JD is identical to
production's model. Skyfield's derived UTC epoch label is
`2000-06-27T18:50:19.733582Z`; production's epoch is
`2000-06-27T18:50:19.733568Z`, a 14 µs display/construction difference.
Both SGP4 records use `mu=398600.8 km³/s²` and Earth radius `6378.135 km`
(WGS72).
The station coordinates are WGS84 geodetic latitude, east-positive longitude,
and ellipsoidal height in metres. Skyfield uses `wgs84.latlon(...,
elevation_m=...)`, geometric `.altaz()` without refraction, and no planetary
ephemeris. Both paths use a 10° geometric elevation mask.

Skyfield uses its [bundled timescale](https://rhodesmill.org/skyfield/api-load.html)
with no polar-motion table.
Astropy receives a scoped IERS table with Skyfield's own daily DUT1 values
and `xp=yp=0 arcsec`; network EOP downloads are disabled. The values are:

- 2000-06-26: `UT1−UTC=+0.20572409999999763 s`.
- 2000-06-27: `UT1−UTC=+0.20528859999999582 s`.
- 2000-06-28: `UT1−UTC=+0.20485180000000014 s`.
- 2000-06-29: `UT1−UTC=+0.20448189999999755 s`.

The outer dates supply interpolation support, not hold-out access results.
At four checked UTC instants, including an interior instant and case B's end,
maximum Astropy-minus-Skyfield DUT1 residual is `5.362377209e-14 s`.
Zero polar motion is a matching convention, not a claim about actual EOP.

## Comparison method

Production follows TLE → WGS72 SGP4 → TEME → Astropy ITRS → station-relative
ITRS → ENU → geometric elevation. Skyfield evaluates
`(satellite - station).at(t).altaz()`. Pointwise `ΔEl` means production minus
Skyfield elevation. The deterministic grid includes both boundaries, every
60 s in case A or 300 s in case B, and each refined Skyfield crossing at
`−30, 0, +30 s`. Maximum absolute and RMS pointwise residuals, the time of
the maximum, and all near-crossing residuals are in the JSON report.

Skyfield [`find_events(..., altitude_degrees=10.0)`](https://rhodesmill.org/skyfield/api-satellites.html)
supplies raw rise (0),
culmination (1), and set (2) events. Culminations are diagnostics only; no
production maximum elevation exists. A **validation-only** plain bisection
on Skyfield geometric elevation brackets each rise/set at ±5 s, expanding
through ±10, ±20, ±40, ±80 s when needed, then reaches interval width
≤`0.001 s`. It calls neither production `brentq` nor the production access
solver. Every observed event bracketed at ±5 s; final widths were
`0.000610–0.000611 s`. An unbracketed event raises an explicit anomaly.
Complete-window counts are checked before chronological pairing, and paired
intervals must overlap. Clipped/incomplete boundary events stay separate.
`Δt` is production event time minus Skyfield raw or bisected event time.
The report also gives Skyfield elevation-minus-mask at the production time
and production elevation-minus-mask at the bisected Skyfield time.

## Development case A — known equator/Greenwich smoke geometry

Station `(0°, 0°, 0 m)`; UTC interval `2000-06-27T20:00:00Z` to `20:40:00Z`.
Both paths return **one complete access**. Skyfield culminates at
`20:22:58.291995Z`, `20.193095°`.

- Rise: production `20:11:00.879898Z`, Skyfield raw `20:11:01.017592Z`,
  bisected `20:11:00.879347Z`; `Δt_raw=−0.137694 s`,
  `Δt_refined=+0.000551 s`. Skyfield mask at production `+7.611161e-6°`;
  production mask at bisected Skyfield time `−3.671118e-6°`.
- Set: production `20:31:30.103190Z`, Skyfield raw `20:31:30.209798Z`,
  bisected `20:31:30.103292Z`; `Δt_raw=−0.106608 s`,
  `Δt_refined=−0.000102 s`. Opposite-time mask residuals are
  `+1.078688e-5°` and `+6.970104e-6°`, respectively.

Across **47** pointwise samples, maximum `|ΔEl|=5.995204333e-13°` at
`20:37:00Z`, RMS `2.211816874e-13°`. At refined rise/set, `ΔEl` is
`−1.225686219e-13°` / `+9.414691249e-14°`; ±30 s residuals are in the
JSON report. The previous production smoke fixture used synthetic
`UT1−UTC=0`, so its event times differ slightly; that expected result has
not been changed.

## Development case B — non-special station

Station `(35.0°, −120.0°, 250.0 m)`; UTC interval
`2000-06-27T00:00:00Z` to `2000-06-28T00:00:00Z`. Production returns
**seven** windows: **five complete**, one clipped at each boundary. Skyfield
returns the same five complete rise/set pairs, plus an initial set and final
rise without their counterpart inside the interval. Production clipped
windows are `00:00:00–00:10:44.353987Z` and
`23:56:31.505438–00:00:00Z`; Skyfield raw boundary events are
`00:10:44.374378Z` set and `23:56:31.529436Z` rise. They are not paired as
ordinary complete windows.

All five complete passes are in the JSON report with production, raw Skyfield,
and bisected Skyfield rise/set times and both opposite-time mask residuals.
The concise timing results below list **rise/set** `Δt_raw` followed by
**rise/set** `Δt_refined`, in seconds:

- Pass 1, culmination `02:14:21.464624Z` at `13.759443°`:
  raw `−0.028692/−0.004046`; refined `−0.001532/−0.001910`.
  This below-15° pass is retained but excluded from ordinary timing statistics.
- Pass 2, culmination `14:36:45.232712Z` at `28.926670°`:
  raw `−0.049740/−0.030623`; refined `−0.001217/+0.002031`.
- Pass 3, culmination `16:57:38.835823Z` at `74.931037°`:
  raw `−0.025706/−0.011638`; refined `−0.001597/+0.001484`.
- Pass 4, culmination `19:22:18.436059Z` at `87.195762°`:
  raw `−0.006869/−0.035118`; refined `−0.002291/+0.000588`.
- Pass 5, culmination `21:48:57.734499Z` at `67.233318°`:
  raw `−0.030831/−0.031412`; refined `−0.001229/+0.000631`.

Across **325** pointwise samples, maximum `|ΔEl|=9.094947018e-13°` at
`17:00:00Z`, RMS `2.482952300e-13°`. Refined-crossing `ΔEl` for the five
complete passes, rise/set respectively, is `(+1.776e-13,+1.386e-13)`,
`(−1.066e-13,−2.132e-14)`, `(−2.345e-13,+5.347e-13)`,
`(−1.936e-13,+2.167e-13)`, and `(−4.992e-13,+2.132e-14)°`.
The JSON report also retains ±30 s residuals and the two boundary crossings.

## Phase A aggregate and Phase B acceptance freeze

For the **ten ordinary complete-window events** (case A plus B passes 2–5),
maximum absolute production-minus-bisected-Skyfield timing residual is
`0.002291132 s`; RMS is `0.001348384 s`. Maximum absolute pointwise
elevation residual across both cases is `9.094947018e-13°`. Complete-window
counts agree. This very close agreement establishes matched software
conventions for these cases with shared SGP4, not TLE, station, or physical
pass-time accuracy. Skyfield's raw `find_events()` times are discovery
outputs, not sub-millisecond references. Phase A was characterization only:
it enforced no ±2 s or other acceptance limit. The Phase B limits below were
frozen after this development characterization and before any hold-out run.

### Frozen Phase B criteria

The comparison retains the same archived TLE, shared `sgp4==2.27` kernel,
matched Skyfield DUT1 with `xp=yp=0`, WGS84 station convention, and geometric
altitude without refraction. These are **cross-implementation numerical
agreement** criteria for the downstream access calculation. They do not
measure physical pass-time accuracy, TLE prediction accuracy, operational
navigation accuracy, or physical angular accuracy.

- **Genuine crossing count and order:** compare actual in-interval geometric
  10° threshold crossings, not the number of `AccessWindow` containers. Both
  paths must have the same number of genuine rises and genuine sets in the
  same chronological rise/set order, with corresponding events belonging to
  the same physical accesses. A clipped analysis boundary is not a crossing.
  Record every unmatched genuine crossing; any such mismatch fails the
  event-count/order criterion and requires investigation.
- **Ordinary crossing time:** for each corresponding rise and set of a
  complete pass whose Skyfield culmination is `>=15°`, require independently
  `abs(t_production - t_skyfield_bisected) <= 0.020 s`. Use the
  validation-only Skyfield geometric bisection, with final bracket width
  `<=0.001 s`, as the timing reference. The production root-refinement
  setting is `0.01 s`; matched DUT1 disagreement (`5.362377209e-14 s` at
  checked instants) and the 14 µs Skyfield epoch-label difference are small
  against this numerical scale. Phase A had near floating-point pointwise
  agreement and millisecond refined crossing residuals. The 20 ms margin
  reflects the two numerical refinement paths; it is not an estimate of the
  real spacecraft's crossing-time uncertainty.
- **Pointwise elevation:** on the predefined Phase B sample set, require
  `max(abs(elevation_production - elevation_skyfield)) <= 1e-9 deg`.
  The sample set contains the interval start and end, every 300 s from the
  start, and `−30, 0, +30 s` about each Skyfield bisection-refined genuine
  rise/set when inside the interval; duplicate timestamps are removed. This
  is the fixed case-B sampling policy applied to Phase B. The limit leaves
  numerical margin above Phase A's approximately `1e-12°` residual while
  detecting a material implementation mismatch.
- **Near-threshold passes:** when `10° <` Skyfield culmination `<15°`, report
  the pass, detection by each path, and timing residuals if pairable. Classify
  it as a near-threshold diagnostic and exclude it from the primary ordinary
  timing aggregate. A detection disagreement stays visible as a separate
  detection-validation issue requiring engineering interpretation, given the
  known finite 5 s production search step. Exclusion alone does not fail the
  ordinary timing criterion; an unmatched genuine crossing still fails the
  separate event-count/order criterion.
- **Raw event timestamps:** retain `t_production - t_skyfield_raw` from
  `find_events()` as a diagnostic only. No pass/fail decision uses raw search
  timestamps. The earlier provisional ±2 s proposal is retired; see
  [decision 0002](decisions/0002-skyfield-holdout-acceptance.md).

**Frozen but unexecuted Phase B hold-out:** same archived Vanguard 1 TLE;
WGS84 station latitude `−33.5°`, east longitude `+151.2°`, ellipsoidal height
`100.0 m`; UTC interval `2000-06-28T00:00:00Z` through
`2000-06-29T00:00:00Z`; 10° geometric mask. No elevation, event, or access
result for that station/interval has been calculated or recorded. **Hold-out
status: defined and acceptance criteria frozen; not yet executed.**

The normal Phase A test checks the two-case registry before it runs; the
southern-hemisphere hold-out is present only as this written fixture and has
no executable case in the Phase A registry. No Phase B expected values or
runner are introduced by this criteria freeze.

Earlier matched split-UT1 Vallado frame verification and its documented
direct printed-vector x-position overrun of 3.17 mm remain unchanged; see
[verification](verification.md). GMAT secondary cross-tool/cross-model
comparison, physical orbit-prediction accuracy, and temporal coverage are
future work.
