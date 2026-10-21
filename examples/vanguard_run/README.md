# Archived Vanguard 1 run-output example

[`config.json`](config.json) is [input schema 1.1](../../docs/input-schema-v1.md)
and holds exact 69-character Vallado/python-sgp4 2.27
catalogue 00005 TLE lines and source label, the `2000-06-27T20:00:00`–`20:40:00`
UTC analysis interval, two synthetic fixed WGS84 stations at `(0°,0°,0 m)` and
`(1°N,1°E,0 m)`, the 10° mask, 5 s event grid and 0.01 s root setting.
The config explicitly selects [`test_only_eop.json`](test_only_eop.json), a
**test/reproducibility-only** zero UT1−UTC/polar-motion IERS table at MJD
51722–51723. The loader resolves it relative to `config.json`, snapshots its
values and hash, and `run_analysis()` scopes it for this run. It is an
internal integration/output-contract case, not independent physical validation.

The saved [JSON result](run.json) has schema `1.1`, status `SUCCESS`,
one window for each station, no validity notices, and one merged coverage
interval: `1229.2680210995704 s`, fraction `0.5121950087914875`, longest gap
`660.8317878096642 s`. The [CSV bundle](csv/) encodes the same run in six
fixed files. `source_revision` is `null` because no build revision was supplied;
the run code does not query Git or add a clock-based field.

SHA-256 of the saved Windows-generated UTF-8 files (LF line endings):

```text
822ee68dd955add87e2d00c60b310140976dde560f1afd2698f93355dae7e9d99  config.json
bd3769c7c5f55131e4ca5472e4787daaa9f2674502b01c9bbdbd573a4f77e824  test_only_eop.json
cde21a989102fbac56404f23945f60db5b5cb1024bc8f30da3a61ef67f99e33  run.json
8cd3a94b936225b77107ea10d2f52976d675482ec188f024217e347cf0ad2c8d  csv/run.csv
cba1a069805044ffdba6203a42181eca55904d1128c7dcdc90cf08c72d6ea09f  csv/stations.csv
f11ca2ae57bbadd3faeb1d9d6c1752dc91d5229ea6cdf01aa04a9cf12b8f6d73  csv/access_windows.csv
985fdda5ff9fe663b8f21d9df22997e229873a8ff8f5e3ca3d3b699d3fc132e8  csv/coverage.csv
8a562f895f9366f72f9fb49ae370a516113430196e05be3261a96f6866ff1132  csv/union_intervals.csv
691e82a56d6a4dc4a94d6db5c0eea7b166f9570e637b4db6a317de786efc62fe  csv/warnings.csv
```

The [run tests](../../tests/test_run.py) load the archived config and execute
it twice without test-side EOP setup, requiring byte-identical reruns on the
same platform. Only the schema/provenance bytes above changed in this fix;
all saved access and coverage values remain intact.
Across platforms, the exact saved bytes are checked for every field except
optimizer-derived maximum elevation and peak time. Those two fields retain the
predeclared MA-04 peak limits (`1e-5 deg`, `0.02 s`) against this saved example;
all other JSON bytes and CSV fields must match exactly. Linux CI exposed
last-bit peak differences from the Windows-generated files without changing
entry/exit, duration, coverage or provenance. The hashes above identify the
saved files, not a promise of cross-platform identical optimizer bits.
