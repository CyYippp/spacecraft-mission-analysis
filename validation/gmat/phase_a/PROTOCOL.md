# GMAT Phase A same-trajectory contact comparison — frozen setup

The parent plan froze event criteria before any GMAT contact run. Execution
became eligible only after the corrected ICRF transfer position gates passed
on 2026-10-23. The existing 1 s and 0.5 s STK ICRF files are the only
trajectories for this comparison. Both are derived from the same production
WGS72 SGP4 TLE trajectory; Phase A does not independently verify SGP4.

Analysis interval: 2000-06-27 20:00:00–20:40:00 UTC. Two observers are the
canonical archived stations, geodetic (0°N, 0°E, 0 m) and (1°N, 1°E, 0 m),
with east-positive longitude. The production reference is the unmodified
canonical `examples/vanguard_run/run.json`, generated under its test-only
explicit zero UT1−UTC/xp/yp EOP input.

For each GMAT run, use Earth-centered STK propagation across the padded file
span, then one manual ContactLocator search over exactly the analysis
interval. Configure both GroundStations as `Spherical` positions with
`HorizonReference = Ellipsoid`, latitude/longitude/height as above (height
in km), `DataSource = Constant`, and `MinimumElevationAngle = 10` degrees.
Configure one ContactLocator targeting the imported spacecraft, both
observers, no additional occulting bodies, `UseEntireInterval = false`,
explicit UTC initial/final epochs, `UseLightTimeDelay = false`,
`UseStellarAberration = false`, `StepSize = 1` s, `RunMode = Manual`,
`WriteReport = true`, and `Legacy` UTC report. Run `FindEvents` once per
transfer file; preserve each script, raw report, stdout/stderr and log.

The installed GMAT R2026a `ContactLocator.html` says the locator is
SPICE-based and uses environmental data parallel to core GMAT. Match GMAT's
core Earth shape to its bundled SPICE planetary constants kernel:
`EquatorialRadius = 6378.1366 km`, `Flattening = 0.00335281310845547`,
with `SolarSystem.PCKFilename` pointing to the installed
`SPICEPlanetaryConstantsKernel.tpc`. This is **not** the exact production
WGS84 ellipsoid (`6378.137 km`, reciprocal flattening `298.257223563`).
Retain the installed GMAT EOP and time/kernel files, recording their identity
and SHA-256. Do not retune Earth or EOP after event exposure. The resulting
Earth shape and orientation boundary must be considered when interpreting
contact residuals; do not assign all residual to trajectory interpolation.

Acceptance, separately for each station: same count/order of genuine access
intervals and physical correspondence; each AOS/LOS absolute residual
≤0.25 s; each duration absolute residual ≤0.50 s. Then compare the 1 s
versus 0.5 s GMAT event times, requiring maximum corresponding shift
≤0.02 s. The position-convergence gate is separate and does not replace
this event-shift requirement. These limits measure cross-tool agreement,
not physical pass-time accuracy. If any criterion fails, retain evidence and
stop before Phase B or any setting change.
