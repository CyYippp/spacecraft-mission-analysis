# Validation status — Skyfield development and hold-out comparison

The analytic access tests are **verification**, and the archived Vanguard 1
smoke test is **internal integration verification**. Phase A characterized two
development cases; Phase B tested a frozen hold-out. Both are **downstream
cross-implementation validation with a shared SGP4 kernel**.
Skyfield 1.55 constructs its `EarthSatellite` through the same installed
`sgp4==2.27` package used by production. Neither phase independently validates
SGP4 propagation or operational orbit prediction. Installed versions: Skyfield 1.55, sgp4 2.27, Astropy
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
culmination (1), and set (2) events. Culminations were diagnostics only in the
frozen Phase A/B comparisons; production maximum elevation was added later and
those saved artifacts do not validate it. A **validation-only** plain bisection
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

**Pre-execution frozen Phase B fixture:** same archived Vanguard 1 TLE;
WGS84 station latitude `−33.5°`, east longitude `+151.2°`, ellipsoidal height
`100.0 m`; UTC interval `2000-06-28T00:00:00Z` through
`2000-06-29T00:00:00Z`; 10° geometric mask. At the criteria-freeze commit,
**hold-out status was: defined and acceptance criteria frozen; not yet
executed.** The first execution and its result are recorded below.

The normal Phase A test checks the two-case registry before it runs; the
southern-hemisphere hold-out was present only as this written fixture at the
criteria freeze and has never been added to the Phase A registry. The Phase B
runner is explicitly invoked and is not run by normal pytest or CI.

## Phase B first-observed hold-out result — PASS

The fixture and all criteria above were frozen in merged Decision 0002 before
any hold-out result was exposed. The already frozen pointwise sampling rule
was used unchanged: 300 s grid including both boundaries, plus the bisected
Skyfield genuine crossings at `−30, 0, +30 s` within the interval, with
identical timestamps removed. The validation-only runner was committed before
execution. An initial launch stopped in an EOP-only preflight: Astropy needed
June 30 as interpolation support for the exact June 29 end. No Phase B orbit,
elevation, event, or result artifact existed at that point. Commit `fdaa200`
added that support day with the same Skyfield DUT1, scoped offline IERS,
zero-polar-motion convention; the subsequent first numerical execution used
source commit `fdaa2002b733dbc937312aa558d74bfaeec11000` and completed
on 2026-10-16 at `15:35:59.708412Z`. No acceptance or production setting was
changed.

The complete first-observed [machine-readable result](../tests/validation/phase_b_results.json)
contains every event, raw and bisected time, access window, pairing, pointwise
sample, and criterion status. Its SHA-256 is
`a521e8e859e2b799f1ead7b5b295ba1ff4afacac0c24ec1530a24e9bc3b20fc6`.
The archived TLE fixture SHA-256 was
`40382ec8a43d7f5e410de127103d1faed9fd35d5e0d4ad0a496ab799bde087bb`;
the unchanged Phase A artifact SHA-256 was
`7472063e8ae304dc10948a712cabdebdf2d570753f08c09884cf5b35914fb3a4`.

Skyfield's bundled daily `UT1−UTC` values, in seconds, were June 26
`+0.20572409999999763`, June 27 `+0.20528859999999582`, June 28
`+0.20485180000000014`, June 29 `+0.20448189999999755`, and June 30
`+0.20424069999999972`. The outer dates support interpolation; June 30 is
needed at the hold-out end. At the start, an interior instant, and the end,
the maximum absolute Astropy-minus-Skyfield DUT1 mismatch was
`4.482525462e-14 s`. Both paths used `xp=yp=0`, geometric altitude without
refraction, and the same `sgp4==2.27` WGS72 propagation kernel.

- **Event sequence — PASS:** production and Skyfield each found five complete
  passes, five genuine rises, and five genuine sets. Both sequences alternate
  rise/set in the same order; the five access intervals correspond uniquely.
  No interval was clipped and no genuine crossing was unmatched.
- **Ordinary timing — PASS:** four passes had Skyfield culmination `>=15°`,
  yielding eight independently checked rise/set events. Maximum absolute
  production-minus-bisected-Skyfield difference was `0.001921201 s` and RMS
  was `0.000832603 s`, against `<=0.020 s` per event.
- **Pointwise elevation — PASS:** across 319 frozen samples, maximum absolute
  production-minus-Skyfield geometric elevation difference was
  `1.108446668e-12°` at `2000-06-28T09:50:00Z`; RMS was
  `2.812810257e-13°`, against `<=1e-9°`.
- **Near-threshold diagnostic:** pass 5 culminated at `14.373091122°`.
  Both implementations detected and uniquely paired its rise and set. The
  refined differences were `+0.001616865 s` and `+0.000247823 s`; both are
  reported but excluded from the ordinary timing aggregate. Its raw
  Skyfield set-time difference was `−0.106258177 s`, illustrating why raw
  `find_events()` timestamps remain diagnostic only.

The five Skyfield culmination elevations were `34.595140988°`,
`66.932373145°`, `86.074007220°`, `70.584128757°`, and `14.373091122°`
in chronological order. The **overall Phase B disposition is PASS** for the
frozen downstream numerical agreement criteria. This does not establish the
real spacecraft's pass times, physical angular accuracy, independent SGP4
accuracy, or operational navigation performance. At the time of the
Skyfield hold-out, GMAT comparison and physical orbit-prediction accuracy
remained future work; bounded GMAT Phase A evidence is recorded below.

Earlier matched split-UT1 Vallado frame verification and its documented
direct printed-vector x-position overrun of 3.17 mm remain unchanged; see
[verification](verification.md).

## GMAT R2026a same-trajectory event comparison — Phase A PASS

This is an independent **event-location implementation** using GMAT's
SPICE-based ContactLocator on a production-generated STK ICRF trajectory.
It is not independent SGP4 propagation evidence or an orbital-truth test.
The original STK `Fixed` transfer failed its same-state gate. The first ICRF
sample gate also remains formally failed under its frozen position-and-
velocity criteria. Installed R2026a documentation then established that
STK-propagated velocity is derived from the position-interpolation
polynomial, rather than guaranteed to reproduce supplied TimePosVel
velocities. [Decision 0004](decisions/0004-gmat-stk-position-transfer-gate.md)
preserved that failure and froze corrected continuous-time position tests.

At 13 predeclared exact-node, midpoint and other fractional UTC epochs,
GMAT's 1 s STK trajectory differed from direct production SGP4→TEME→
validation-only GCRS position by at most `7.17963611987e-6 km` against
`0.001 km`. Its 1 s versus 0.5 s GMAT position difference was at most
`1.63010147317e-6 km` against `0.0001 km`. Both passed, allowing Phase A.
The [transfer record](../validation/gmat/icrf/corrected_position/README.md)
links every reference and GMAT vector, residual and raw report. These are
numerical transfer-fidelity results, not physical orbit accuracy.

In the frozen 20:00–20:40 UTC Vanguard interval, both production and GMAT
found one corresponding 10° access at each of the two archived stations.
With the 1 s transfer, maximum absolute AOS/LOS residual was
`0.050494707 s` (limit `0.25 s`) and maximum absolute duration residual
was `0.050373770 s` (limit `0.50 s`). With the 0.5 s transfer and unchanged
1 s ContactLocator step, the reported AOS/LOS shift was `0.000 s` at
GMAT's 1 ms report resolution (limit `0.02 s`). Phase A passes the frozen
count/order, event timing, duration and transfer-sensitivity checks. The
[Phase A evidence](../validation/gmat/phase_a/README.md) links raw GMAT
scripts/reports and machine-readable signed residuals.

GMAT's bundled SPICE PCK Earth ellipsoid and installed orientation/time
inputs differ from production WGS84 and the explicit synthetic zero-EOP
snapshot. The validation record gives their identities and hashes. Event
residuals therefore include station/frame/environment differences; the
millimetre-scale trajectory-transfer result does not make them physical
pass-time errors. MA-07 remains **PARTIALLY VALIDATED** because Phase B's
independently propagated different-dynamics diagnostic and physical-orbit
validation remain outstanding. No production model, archived scientific
artifact or original acceptance threshold changed.
