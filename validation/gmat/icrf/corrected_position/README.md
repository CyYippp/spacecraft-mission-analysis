# Corrected ICRF position-transfer qualification — PASS

The [protocol](PROTOCOL.md) fixed all 13 epochs and both limits before the
corrected comparisons. Installed GMAT R2026a `Propagator.html` states that
its default STK position interpolation uses a seventh-order Hermite-Newton
divided-difference polynomial from position values only; propagated
velocity is the derivative of that polynomial. The original exact-grid
position-and-velocity gate remains **FAILED** and archived in `../`.
The velocity residuals below are diagnostic, not a pass/fail test.

At each listed UTC epoch on 2000-06-27, the direct reference was computed
anew from the canonical archived TLE with production WGS72 SGP4 and a
validation-only Astropy TEME→GCRS transformation using the canonical
explicit test-only EOP snapshot. It was not interpolated from either STK
file. GCRS-to-STK ICRF is the provisional geocentric ICRS-aligned transfer
convention of Decision 0003. Both GMAT runs reported the intended UTC labels.

| UTC | GMAT 1 s − direct position norm (km) | GMAT 1 s − 0.5 s position norm (km) |
| --- | ---: | ---: |
| 20:00:00.000 | 1.20175591655e-10 | 1.81898940355e-12 |
| 20:00:00.500 | 2.06933311668e-10 | 2.10532799187e-10 |
| 20:03:17.123 | 3.79315901548e-7 | 1.42557100708e-7 |
| 20:10:00.000 | 1.81987736523e-12 | 1.13686837722e-13 |
| 20:10:00.500 | 1.28631641069e-6 | 1.28627025770e-6 |
| 20:17:43.371 | 1.07935151132e-6 | 8.60473555958e-7 |
| 20:20:00.000 | 1.92932961323e-12 | 1.81898940355e-12 |
| 20:20:00.500 | 8.70164201379e-7 | 8.70110539329e-7 |
| 20:30:00.000 | 2.19510463380e-6 | 1.81898940355e-12 |
| 20:30:00.500 | 3.23296442097e-6 | 1.15766416977e-6 |
| 20:33:08.777 | 4.21268495372e-6 | 3.81206716494e-8 |
| 20:39:59.500 | 6.41632611844e-6 | 1.63010147317e-6 |
| 20:40:00.000 | 7.17963611987e-6 | 2.41701532394e-12 |

**Production-reference position gate: PASS.** Maximum `7.17963611987e-6 km`
(about 7.18 mm), frozen limit `0.001 km` (1 m).

**Interpolation-convergence position gate: PASS.** Maximum
`1.63010147317e-6 km` (about 1.63 mm), frozen limit `0.0001 km` (0.1 m).
These are numerical validation-transfer fidelity limits, not physical orbit
accuracy. All direct reference vectors, both GMAT vectors, signed components,
and velocity diagnostics appear in [`position_gate_1s.json`](position_gate_1s.json)
and [`position_gate_0p5s.json`](position_gate_0p5s.json). The
[per-epoch position CSV](position_vectors.csv) places the direct production
and both GMAT vectors beside the two position residual norms. Representative
GMAT-minus-direct velocity norms at 20:00, 20:20 and 20:40 were
`0.001141886`, `0.000448211` and `0.000401191 km/s`, respectively. No
velocity acceptance test was applied; the documented semantics do not by
themselves explain each residual quantitatively.

The original 2521-row 1 s file has SHA-256
`25947878388a27baaad24370f75df1691740b6514842ddb7a4e3a3aef11dacd7`.
The separate [5041-row 0.5 s file](vanguard_icrf_0p5s.e) has SHA-256
`73b0d8648b63df8e36284d518447b221bfae2639d24670a4398a5acbc7824c93`.
Both cover 19:59–20:41 UTC and have identical model and frame conventions;
[`half_second_manifest.json`](half_second_manifest.json) records generator,
source and content hashes. Scripts, GMAT raw reports, stdout/stderr and logs
for both gates are retained here.

**Disposition:** ICRF transfer approved for the bounded Phase A ContactLocator
comparison. This does not approve SGP4 physical accuracy, equate GCRS and
every ICRF implementation, or validate event timing by itself. The separate
[Phase A result](../../phase_a/README.md) assesses that event comparison.
