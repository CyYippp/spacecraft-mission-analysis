# GMAT R2026a STK ICRF transfer trial — failed propagated-sample gate

**Historical gate result:** FAIL under its original position-and-velocity
criteria. Installed GMAT R2026a documentation was then reviewed, and
[Decision 0004](../../../docs/decisions/0004-gmat-stk-position-transfer-gate.md)
froze corrected continuous-time **position** gates. Both corrected gates
subsequently passed; the transfer is now qualified for the bounded Phase A
event comparison. The original failure and all values below remain intact.

The [protocol](PROTOCOL.md) froze the five conversion epochs and all numerical
limits before the first comparison. The installed GMAT R2026a
`docs/help/html/EphemerisFile.html` and `Propagator.html` document STK `ICRF`
for an Earth-centered ephemeris; the propagator guide maps STK ICRF to GMAT
ICRF and says it is supported for all central bodies. This is a validation
transfer trial, not production code or a physical orbit-accuracy claim.

## Conversion and transfer file

`check_transfer.py` uses the canonical archived config, production WGS72
SGP4 TEME states, Astropy 7.2.1 `TEME(obstime=UTC).transform_to(GCRS(obstime=UTC))`,
and the config's explicit test-only EOP snapshot. Its comparison is Skyfield
1.55 `EarthSatellite.at()` geocentric position/velocity for the same TLE and
times, with bundled time data and no network fetch. Skyfield shares `sgp4`
2.27, so this verifies conversion agreement only. GCRS-to-STK ICRF is a
provisional geocentric ICRS-aligned convention, not an assertion of exact
frame-theory identity.

The [full result](transfer_check.json) records both vectors and component
residuals. Astropy-minus-Skyfield Euclidean residuals were:

| UTC | Position (km) | Velocity (km/s) |
| --- | ---: | ---: |
| 19:59 | 1.41825026143e-7 | 7.99917021713e-8 |
| 20:00 | 1.42436482653e-7 | 7.98232308596e-8 |
| 20:20 | 1.23335345126e-7 | 7.30586270250e-8 |
| 20:40 | 6.49823077518e-8 | 6.08206774811e-8 |
| 20:41 | 6.36876381974e-8 | 6.02258698318e-8 |

**PASS:** each is below the frozen 0.001 km and 1e-6 km/s limits.

Only after that pass, `generate_icrf.py` wrote the 2521-row, 1 s STK file
[`vanguard_icrf_1s.e`](vanguard_icrf_1s.e), 19:59–20:41 UTC inclusive, with
60 s padding around the 20:00–20:40 analysis interval. It declares Earth,
`CoordinateSystem ICRF`, km and km/s. Its SHA-256 is
`25947878388a27baaad24370f75df1691740b6514842ddb7a4e3a3aef11dacd7`;
generation metadata is in [`ephemeris_manifest.json`](ephemeris_manifest.json).
The exact generator source as executed is retained in
[`generator_executed.txt`](generator_executed.txt); subsequent formatting of
the Python working copy did not change or regenerate the STK file.

## GMAT gates

`check_parser_gate.py` requested both endpoints via
`GetEphemStates('STK', ..., 'UTCGregorian', EarthICRF)`. The [raw report](icrf_parser_report.txt)
and [machine result](icrf_parser_gate.json) show correctly labelled UTC
endpoints. Position residual norms were `5.68434188608e-13` and `0 km`;
velocity norms were `4.44089209850e-16` and `8.89911452411e-16 km/s`.
**PASS** against 1e-6 km and 1e-9 km/s.

`check_sample_gate.py` then propagated GMAT's STK spacecraft to exact file-grid
times. Its first launch used cumulative elapsed targets for successive GMAT
`Propagate` steps and attempted to step beyond the ephemeris span; the original
script, raw stdout, stderr, log and partial report are retained in
[`attempt1_script_error/`](attempt1_script_error/). It produced no completed
sample-gate comparison. The script was corrected to take 60, 1200 and 1200 s
successive steps, without changing the ephemeris, epochs, frame, values or
limits. The [final raw report](icrf_sample_report.txt), [GMAT stdout](icrf_sample_stdout.txt),
and [machine result](icrf_sample_gate.json) retain the completed gate:

| UTC | Position residual (km) | Velocity residual (km/s) | Status |
| --- | ---: | ---: | --- |
| 20:00 | 1.20175591655e-10 | 0.00114188631140 | FAIL |
| 20:20 | 2.01590304317e-6 | 0.000448211655846 | FAIL |
| 20:40 | 2.39321279795e-6 | 0.000401191380828 | FAIL |

The frozen limits are **1e-6 km position** and **1e-9 km/s velocity** at
each epoch. UTC labels match. All three velocities fail; two positions also
fail. The difference is not report rounding. The exact GMAT STK interpolation
or frame semantics causing the velocity difference are not established; no
compensation or threshold change was attempted.

**Disposition: ICRF is not approved for Phase A ContactLocator.** The
EarthFixed-versus-ITRS diagnostic, ContactLocator and Phase B were not run.
No alternate frame was tried. Production APIs, event criteria and MA-07
status remain unchanged. The old rejected `Fixed` evidence is retained in
[`../fixed_gate_diagnostic/`](../fixed_gate_diagnostic/).
The [SHA-256 manifest](sha256_manifest.json) covers all files in this trial,
including the failed first script attempt; run `../hash_evidence.py` to
regenerate it.

The preceding disposition describes the first frozen gate **at the time it
was run**. The original pre-correction manifest is preserved as
[`historical_sha256_manifest.json`](historical_sha256_manifest.json). Current
qualification and ContactLocator evidence are in
[`corrected_position/`](corrected_position/) and [`../phase_a/`](../phase_a/).
