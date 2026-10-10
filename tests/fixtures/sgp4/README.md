# SGP4 reference fixture

`vanguard_1_00005.json` is the minimum archived data needed by the current
automated vector test. It preserves the exact 69-character TLE lines and all
printed vector digits. The numbers were transcribed from the files distributed
with `python-sgp4==2.27`:

- TLE: [`sgp4/SGP4-VER.TLE`, case 00005](https://github.com/brandon-rhodes/python-sgp4/blob/2.27/sgp4/SGP4-VER.TLE), SHA-256 of the installed file `d246d1d9d768ace445a38a965713fa9ba52d80fd8a41a0502ff83d7acffe2881`.
- Vector: [`sgp4/tcppver.out`, case 5, +360.00000000 minutes](https://github.com/brandon-rhodes/python-sgp4/blob/2.27/sgp4/tcppver.out), SHA-256 of the installed file `7a46d8cd6dfd6eb65b3c662cb1ebd97f5e5cc5a2a2f5cf7c7767b9f1d0497e7e`.

Catalogue ID: **00005 (Vanguard 1)**. TLE epoch:
`2000-06-27T18:50:19.733568000` UTC. Propagation input: **+360 minutes**,
equivalent to `2000-06-28T00:50:19.733568000` UTC on this non-leap-second day.
Expected TEME position: `(-7154.03120202, -3783.17682504,
-3536.19412294)` km. Expected TEME velocity: `(4.741887409,
-4.151817765, -2.093935425)` km/s. The output file prints position to
8 decimal places and velocity to 9. Its trailing calendar timestamp is
derived from a recombined Julian-date float; the offset field is the time
fixture used here.

The files are from the MIT-licensed
[python-sgp4 project](https://github.com/brandon-rhodes/python-sgp4/blob/2.27/LICENSE).
This repository retains only the case values, not the complete upstream
verification datasets. See [verification](../../../docs/verification.md) for
the acceptance tolerances and observed residuals.
