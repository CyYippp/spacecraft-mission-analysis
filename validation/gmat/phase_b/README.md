# GMAT R2026a independent numerical propagation diagnostic

**Phase B: completed diagnostic, not an orbital-truth validation.** The
[protocol](PROTOCOL.md) was fixed before the initial-state gate and numerical
residuals were examined. All four GMAT scripts were generated and hashed at
that point. The [runner](run_diagnostic.py) enforced the initial-state gate,
one base trajectory, one max-step refinement, and contact execution only after
sampled-state review. The installed console build was Mar 26 2026 15:02:55.
The bundled `data/gravity/earth/EGM96.cof` SHA-256 is
`3e8806223250224d3c1333a010eb5c2cc5a212a56ccee4024db81b9d889db5ea`.
Its startup mapping and installed ForceModel documentation support the EGM96
file directly.

The initial UTC epoch was **2000-06-27T20:00:00Z**. The production WGS72 SGP4
state was transformed from TEME through the Phase A checked Astropy GCRS
conversion, using the canonical explicit EOP table. GMAT was initialized
directly in `EarthICRF`, not through STK. The intended position was
`(-9557.268433756957, 3166.238374728190, 823.863275535456) km`; velocity
`(-1.3289096210919524, -4.5449373123392434, -3.2162795468301510) km/s`.
GMAT reported `(-9557.268433756954, 3166.238374728190,
823.8632755354558) km` and `(-1.3289096210919524, -4.5449373123392443,
-3.2162795468301506) km/s` at that same UTC epoch. The transfer residual
norms were `3.63975473046e-12 km` and `9.93013661299e-16 km/s`, passing
the frozen `1e-6 km` and `1e-9 km/s` limits. See [raw gate report](gate_report.txt)
and [parsed result](gate.json).

GMAT used Earth-only EGM96 degree/order 4/4 with tides, drag, SRP, third-body
point masses, relativity, and maneuvers disabled. The integrator was
PrinceDormand78 with RSSStep error control, Accuracy `1e-12`, initial step
`10 s`, minimum step `0.001 s`, maximum step `60 s`, and stop on accuracy
violation. The [base](base.script) and [refined](refined.script) scripts differ
only in report filename and maximum step (`60→30 s`). At 40 minutes, the
[base](base.json) and [refined](refined.json) final states differed by
`2.71396590939e-6 km` and `2.42434507453e-9 km/s`, passing the frozen
`0.001 km` and `1e-6 km/s` numerical-repeatability limits. This convergence
does not assess force-model accuracy. Raw reports and console logs are retained.

## Nine-epoch cross-model state comparison

These are GMAT-minus-production norms in the common validation-only inertial
convention. The [CSV](state_comparison.csv) and [JSON](state_comparison.json)
give every full position/velocity vector and signed Cartesian residual; the
[base raw report](base_report.txt) is the GMAT source. There is deliberately
no SGP4-versus-GMAT residual magnitude acceptance limit.

| Minutes | Position norm (km) | Velocity norm (km/s) |
| ---: | ---: | ---: |
| 0 | 3.63975473046e-12 | 9.93013661299e-16 |
| 5 | 0.330994212253 | 0.000375495659450 |
| 10 | 0.622636047105 | 0.000757635272864 |
| 15 | 0.865733500809 | 0.00115260401642 |
| 20 | 1.08558442595 | 0.00155999941820 |
| 25 | 1.35201240357 | 0.00197736201783 |
| 30 | 1.75100369717 | 0.00241429048683 |
| 35 | 2.32543431099 | 0.00291454637623 |
| 40 | 3.05814740466 | 0.00355989458257 |

All nine reports have exact requested timestamps and finite states. Both
sampled residual norms increase monotonically, with no unexplained sampled
jump. This does not establish continuity between samples. At 40 minutes the
signed position residual is `(-2.420797369, -1.261007293,
-1.379081672) km`; the negative x component is largest in the fixed inertial
axes. These components alone are not a radial/along-track/cross-track
diagnosis. The position and velocity differences are much larger than the
observed integrator-refinement differences. They are model divergence, not a
failure against an invented agreement criterion.

## Model boundary

| Aspect | Production | GMAT Phase B |
| --- | --- | --- |
| Initial state | WGS72 SGP4 TEME→GCRS at 20:00 UTC | Same Cartesian state directly in EarthICRF |
| Propagation | TLE-fitted SGP4 analytical model | Numerical PrinceDormand78 |
| Earth gravity | SGP4 internal WGS72 model | Bundled EGM96 harmonic 4×4 |
| Drag | SGP4 BSTAR model parameter | No physical drag model |
| SRP / third bodies | No separately configured physical SRP or third-body force model in this near-Earth SGP4 run | Both disabled |
| Comparison frame | Validation-only GCRS convention | EarthICRF |
| Access geometry | Production solver, WGS84 station/EOP fixture | GMAT SPICE ContactLocator, installed Earth/EOP environment |

BSTAR cannot uniquely determine Cd, area, mass, or a ballistic coefficient;
those properties were not invented for GMAT. The Phase A Astropy/Skyfield
same-SGP4 transfer check found at most `1.42436482653e-7 km` position and
`7.99917021713e-8 km/s` velocity difference at its five sampled epochs; it
does not establish perfect identity between GMAT EarthICRF and Astropy GCRS.
Likewise, GMAT's Earth constants, station ellipsoid, and Earth-orientation
inputs differ from production. Neither trajectory is designated truth.

## Contact consequence

The numerical trajectory produced one 10° event at each Phase A station.
The [GMAT report](contacts_report.txt), [parsed source](contacts.json), and
[signed comparison](contact_comparison.json) preserve both event sequences.
GMAT-minus-production differences were:

| Station | Production AOS / LOS UTC | GMAT AOS / LOS UTC | ΔAOS / ΔLOS (s) | Δduration (s) |
| --- | --- | --- | --- | ---: |
| Greenwich | 20:11:00.831787810 / 20:31:30.099808909 | 20:11:00.779 / 20:31:30.661 | −0.052787810 / +0.561191091 | +0.614325800 |
| 1N/1E | 20:12:13.258505293 / 20:30:57.478295163 | 20:12:13.170 / 20:30:58.068 | −0.088505293 / +0.589704837 | +0.678050830 |

Production durations were `1229.2680210995704 s` and
`1124.2197898697889 s`; GMAT reported `1229.8823469 s` and
`1124.8978407 s`. These are diagnostic cross-model consequences; the Phase A
0.25 s / 0.50 s same-trajectory limits do not apply. ContactLocator also
uses its installed SPICE time/orientation and station geometry, so event
differences cannot be attributed solely to orbit dynamics.

Phase A independently exercised event location on an imported production
trajectory. Phase B independently exercised numerical dynamics under a
deliberately different, documented force model. Neither is independent
same-model SGP4 verification or observed-orbit accuracy evidence.
