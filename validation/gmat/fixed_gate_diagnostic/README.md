# GMAT R2026a fixed-STK diagnostic (uncommitted working evidence)

This is a diagnostic of the failed fixed-frame compatibility gate, not Phase A
access validation. No ContactLocator or Phase B run was made. The executable was
`C:\Users\Cyrus\Applications\GMAT\R2026a\bin\GmatConsole.exe` on Windows
10.0.26200 (build date Mar 26 2026 15:02:55). Scripts ran from GMAT's `bin`
directory using `--logfile <path> --exit --run <script>`.

## Original evidence

The four copied raw files retain these SHA-256 values:

The [full manifest](sha256_manifest.json) hashes every retained diagnostic
file; run `../hash_evidence.py` to regenerate it. The four anchor hashes below
match the pre-trial evidence.

| File | SHA-256 |
| --- | --- |
| `production_fixed_1s_gate.e` | `c9925ec177179c2558a3c5f61fc50ae5faa04cba27af91ed9f9566ade3c2d693` |
| `fixed_import_gate.script` | `70915e20f6e953277087a80c72b98400efbdb5d27ef9b04586b8893e35b6d7a3` |
| `fixed_import_report.txt` | `26b85e2086c4fdb9f54ba03af44b7cf91277876e87a1a7bb1f7efd9f1419a2cd` |
| `gmat_stdout.txt` | `06a002c6db5d29a8544c0e8e67f847978879125b294c87ac554c8e2b51291cc1` |

The 121-point file spans offsets 0–120 s at 1 s spacing. Its ScenarioEpoch is
`27 Jun 2000 19:59:00.`; `TimeFormat` and interpolation fields are absent;
`CoordinateSystem Fixed` and `DistanceUnit Kilometers` are explicit. Row 60 is
`20:00:00 UTC` and has the production ITRS position and velocity, to file
serialization precision. GMAT parses the epoch as `19:59:00.000` and returns
the raw endpoint states through `GetEphemStates('STK', ..., EarthFixed)`.

## Measurements

`diagnosis.json` is reproduced by running `diagnose_fixed_gate.py`. At the
row-60 state, GMAT minus production Earth-fixed position is
`(+0.598120063324, +0.425758202326, +0.000000305810) km`, norm
`0.734178218826 km`. The best-fit Z rotation is `7.29211596240645e-5 rad`,
equivalent to `1.000000131979` sidereal seconds at `7.2921150e-5 rad/s`.
The remaining vector after this rotation is
`(-1.450735e-8, +2.037814e-8, +3.058103e-7) km`, norm `3.068317e-7 km`.

`epoch_trace_report.txt` shows UTC `20:00:00.000`, TAI `20:00:32.000`,
A1ModJulian `21723.33370410164` and `ElapsedSecs = 0` after the 60 s STK
propagation from the `19:59:00` file start. Before propagation, the spacecraft
still has its default state; assigning its epoch does not import the ephemeris.
`GetEphemStates` returns the file endpoints in both EarthFixed and
EarthMJ2000Eq, and returns TAI endpoints 32 s after UTC.

The GMAT startup file selects
`data/planetary_coeff/eopc04_08.62-now` as `EOP_FILE`; no diagnostic script
overrides `Earth.EopFileName` (its documented default is empty). Its rows at
MJD 51722/51723 have UT1−UTC `0.2053382`/`0.2048634 s`, xp
`0.109043`/`0.109610 arcsec`, and yp `0.285471`/`0.284156 arcsec`.
Linear interpolation to `20:00 UTC` gives UT1−UTC `0.2049425333 s`, xp
`0.1095155 arcsec`, yp `0.2843751667 arcsec`. The interpolation is an
estimate from the source rows; GMAT's internal interpolated value was not
directly exposed. Production's explicit EOP fixture has zero for all three.
GMAT's `data/time/tai-utc.dat` and SPICE leap-second kernel both have
TAI−UTC `32 s` for this date, consistent with GMAT's printed TAI epoch.

The `shift_minus1` and `shift_plus1` files change only `ScenarioEpoch` by
−1/+1 s; all state rows are byte-identical. GMAT reports row 60 at
`19:59:59`/`20:00:01`, but the residual norms remain
`0.734178218810`/`0.734178218827 km`. Replacing the original trailing
decimal with `.000` also leaves the reported state unchanged.

`direct_fixed_report.txt` inputs the same row-60 state directly as a GMAT
EarthFixed Cartesian spacecraft at `20:00 UTC`. GMAT returns its EarthFixed
coordinates exactly. Its EarthMJ2000Eq position differs from the
STK-propagated spacecraft by `(-0.230851223, -0.696940004, -0.000011020) km`,
again `0.734178219 km`. This holds GMAT's EOP and time conversion common to
both paths and isolates the discrepancy to the STK fixed-frame import or
propagator interpretation.

## Disposition

**C — STK `Fixed` semantic/propagator mismatch.** The installed GMAT guide's
EphemerisFile section lists permitted STK frames as J2000, ICRF, Earth-only
TrueOfDate, and Sun-only J2000_Ecliptic; it says other frames are disallowed.
The installed Propagator section separately lists `Fixed` as supported, so
the documentation is not consistent on this point. Rejection rests on the
measured same-state compatibility failure, not on a documentation-only claim.
GMAT nevertheless accepts this `Fixed` file and completes the script, then
reports the one-sidereal-second rotated state. The precise internal mechanism
of that rotation is not established. The controlled label shifts, normalized
epoch format, explicit UTC/TAI trace, and direct EarthFixed control rule out
the proposed one-second time-label, leap-second, script sequencing, and
GMAT-versus-production EOP differences as sufficient explanations of the
observed inter-path discrepancy.

The compatibility gate remains failed. No transfer-frame change, contact
search, force-model run, MA-07 status change, or acceptance-criterion change
is made here. A future method needs an explicit engineering decision and a
new known-state import gate.
