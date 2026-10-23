# GMAT Phase A same-trajectory contact comparison — PASS

The [frozen setup](PROTOCOL.md) was executed only after both corrected ICRF
position gates passed. GMAT R2026a (`GmatConsole.exe`, build Mar 26 2026
15:02:55) ran from its installed `bin` directory using `--logfile`, `--exit`
and `--run`. Nonessential Python/MATLAB/Fmincon plugin startup warnings did
not prevent the ContactLocator from running. This is a separate GMAT/SPICE
event-location implementation consuming a production-generated trajectory;
it is **not** independent SGP4 propagation evidence.

The target was the padded Earth-centered STK ICRF Vanguard trajectory.
Analysis was restricted to 20:00–20:40 UTC on 2000-06-27. Both canonical
stations used their exact geodetic latitude, east longitude and 0 m height:
Greenwich `(0°, 0°)` and synthetic 1N/1E `(1°, 1°)`. GMAT stations used
ellipsoid horizons and a constant 10° minimum elevation. ContactLocator
used a 1 s search step, disabled light-time and stellar aberration, no
additional occulting body, and one manual `FindEvents` per file. The
[1 s script](phase_a_1s.script), [0.5 s script](phase_a_0p5s.script),
[raw 1 s report](phase_a_1s_report.txt), [raw 0.5 s report](phase_a_0p5s_report.txt)
and console outputs are preserved. The JSON results were parsed from those
reports, not manually transcribed.

## Frozen event comparison

Each station had one genuine, corresponding, chronologically ordered access
interval in both production and GMAT. The 1 s transfer gave:

| Station | Production AOS / LOS UTC | GMAT AOS / LOS UTC | GMAT−production AOS / LOS (s) | Duration difference (s) |
| --- | --- | --- | --- | ---: |
| Greenwich | 20:11:00.831787810 / 20:31:30.099808909 | 20:11:00.880 / 20:31:30.103 | +0.048212190 / +0.003191091 | −0.045123900 |
| 1N/1E | 20:12:13.258505293 / 20:30:57.478295163 | 20:12:13.309 / 20:30:57.478 | +0.050494707 / −0.000295163 | −0.050373770 |

Production durations were `1229.2680210995704 s` and
`1124.2197898697889 s`; GMAT reported `1229.2228972 s` and
`1124.1694161 s`. The duration criterion uses GMAT's reported duration,
which has finer precision than its displayed millisecond event timestamps.
Maximum absolute AOS/LOS residual was `0.050494707 s` against the frozen
`0.25 s` limit; maximum absolute duration residual was `0.050373770 s`
against `0.50 s`. **Phase A event correspondence and timing: PASS.**

With the 0.5 s imported trajectory and unchanged 1 s ContactLocator step,
both stations again had one corresponding access. GMAT reported the same
AOS/LOS timestamps as the 1 s run. The maximum observed event shift was
`0.000 s` at the report's 1 ms timestamp resolution, below the frozen
`0.02 s` requirement. The reported durations changed by less than
`0.000001 s`. **Event-level transfer sensitivity: PASS at report resolution.**
The distinct [1 s](phase_a_1s.json) and [0.5 s](phase_a_0p5s.json) JSON
records contain all source values, signed and absolute comparisons,
criteria, settings and hashes.

## Earth and time-model boundary

The installed GMAT guide states that ContactLocator uses SPICE environmental
data parallel to GMAT's core propagation configuration. The validation
scripts matched GMAT core Earth shape to the bundled SPICE planetary
constants kernel: equatorial radius `6378.1366 km`, flattening
`0.00335281310845547`; its PCK Earth radii are `(6378.1366, 6378.1366,
6356.7519) km`. Production stations use WGS84 (`6378.137 km`, reciprocal
flattening `298.257223563`), so the ellipsoids are not identical. GMAT used
its installed startup EOP (`eopc04_08.62-now`), planetary PCK/BPC and
SPICE leap-second kernel; production used the archived synthetic zero
UT1−UTC/xp/yp EOP snapshot. [Machine-readable environment metadata](phase_a_1s.json)
records the relevant file paths and SHA-256 values. No installation file was
changed. The residuals include these station/frame/environment differences;
they cannot all be attributed to trajectory interpolation after its
millimetre-scale position gates.
The [environment manifest](environment_manifest.json) additionally hashes
the installed SPICE Earth orientation BPC kernels and planetary SPK loaded
in GMAT's retained console output, without rerunning ContactLocator.

The original STK `Fixed` transfer failure, first ICRF sample-gate failure,
and corrected position qualification remain visible in
[`../fixed_gate_diagnostic/`](../fixed_gate_diagnostic/) and
[`../icrf/`](../icrf/). Phase B independent-dynamics propagation was not
performed in this bounded Phase A execution. MA-07 remains partially
validated: this result is numerical cross-tool event agreement for an
imported production trajectory, not physical pass-time accuracy or an
independent SGP4 check. [SHA-256 manifest](sha256_manifest.json) covers the
Phase A evidence.
