# Run output contract: schema 1.1

`run_analysis(AnalysisConfig) -> AnalysisResult` composes the existing orbit,
frame, station, access and temporal-coverage kernels. `serialize_json()` and
`csv_bundle()` turn that result into deterministic UTF-8 text. No output
serializer performs scientific calculations. Station and window order follows
the supplied configuration and detected UTC order. JSON keys are sorted and
indented; CSV uses stable header order and LF line endings. Neither includes a
wall-clock generation time or random identifier.
Byte-identical reruns are required within a fixed environment. The archived
Windows-generated output is not a cross-platform byte oracle for
optimizer-derived peak elevation/time; see [ISS-008](issues.md#iss-008--cross-platform-peak-snapshot-bytes).

## Status and availability

- `SUCCESS`: computation completed, including a genuine no-pass result.
- `SUCCESS_WITH_WARNINGS`: computation completed, with one or more workflow or
  evidence-envelope warnings.
- `FAILED`: a required propagation or frame computation failed. `station_access`
  and `coverage` are JSON `null`; no partial station result survives. CSV
  `access_windows.csv`, `coverage.csv` and `union_intervals.csv` have headers
  only. `run.csv`, `stations.csv` and `warnings.csv` remain populated.

Structurally invalid configuration raises before a run result is created.
Unexpected software defects are not converted into scientific no-access results.

## JSON

Top-level fields are `schema_version`, `status`, `configuration`, `provenance`,
`notices`, `station_access` and `coverage`. Schema version is `"1.1"`.

`configuration` contains analysis `*_utc` bounds, raw 69-character TLE lines,
TLE catalogue ID, epoch and source, ordered fixed-station WGS84 geodetic
coordinates, elevation mask, coarse/root/peak numerical settings, frozen
7-day TLE-age and 24-hour comparison-duration warning settings, the explicit
Earth-orientation mode and source label, normalized relative table identity
and SHA-256 for `explicit_table` (otherwise JSON `null`), and an optional
externally supplied source revision. The archived config selects its
test-only EOP table; `run_analysis()` scopes the loaded table for that run.
Scientific code does not invoke Git to discover a revision.

`provenance` records project, SGP4, Astropy and SciPy versions, WGS72 SGP4
constants, WGS84 station ellipsoid, TEME SGP4 output frame and Astropy IERS
frame mode (`configured_iers` or `explicit_table`). `notices` use stable `code`, `severity`, `stage`, `message` and
numeric/string `details`. Access windows carry UTC entry, exit and maximum
time, duration seconds, maximum elevation degrees, and clipped flags. Coverage
carries accessible seconds, fraction, merged count, longest-gap seconds and
UTC bounds, plus the union intervals. A successful no-pass run has an ordered
station result with empty window arrays and a real zero-coverage object.

All timestamps are UTC ISO-8601 strings ending in `Z`, with nine fractional
digits. Numeric units are encoded in field names (`_s`, `_deg`, `_m`, `_days`,
`_hours`); `coverage_fraction` is dimensionless.

## CSV bundle

Every run exports the same six files:

- `run.csv`: one row with status, complete scalar run/TLE configuration,
  Earth-orientation mode/source/table identity/hash, provenance and notice count.
- `stations.csv`: one row per configured station with WGS84 geodetic fields.
- `access_windows.csv`: one row per station pass, with entry/exit, duration,
  maximum elevation/time and clipped flags.
- `coverage.csv`: one row when the computation completed, including longest-gap
  bounds; header only after failure.
- `union_intervals.csv`: one row per merged access interval; header only after
  failure or a successful no-pass result.
- `warnings.csv`: one row per notice. `details_json` contains its stable
  machine-readable context as compact sorted-key JSON.

## Human-readable report (proposed v0.1.1)

The installed command also writes `report.html` beside `run.json`. This is a
self-contained, offline presentation of the same `AnalysisResult`: an access
timeline, recorded-window duration comparison, station pass table, combined intervals,
configuration/provenance and notices. The timeline is based on refined event
times recorded in the result; it does not interpolate an elevation curve or
calculate a new orbit product. Plot axes use UTC, tables declare units, and
rounded display values point back to `run.json` for full precision. Failed
runs show their error notices and omit access plots; successful no-pass runs
show zero coverage. Warning runs show an amber status and a summary before the
plots. The report makes no operational or physical-accuracy claim.

The JSON schema remains 1.1 and the six CSV files retain their existing names
and contents. `report.html` joins the staged, no-overwrite output bundle, so
publication failures roll back newly written artifacts. New run provenance
records package version 0.1.1. The archived v0.1.0 example remains unchanged
and does not contain an HTML report.

The [archived example](../examples/vanguard_run/) contains the versioned input
config, its explicitly selected test-only EOP fixture, canonical JSON and full
CSV bundle. The [verification record](verification.md)
separates software-contract checks from physical validation.
