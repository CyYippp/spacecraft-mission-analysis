# Analysis input contract: schema 1.1

[`load_analysis_config(path)`](../src/spacecraft_mission_analysis/input.py) reads
UTF-8 JSON into the existing `AnalysisConfig`; `parse_analysis_config(mapping,
base_dir=...)` provides the same validation for an in-memory mapping. `base_dir`
is required when that mapping names a relative EOP file. The canonical archived
example is [`config.json`](../examples/vanguard_run/config.json). Input schema
`1.1` and [run-result schema `1.1`](run-schema-v1.md) are separate contracts.
Malformed input raises `InputConfigError` before `run_analysis()`; it does not
produce a scientific `FAILED` result.

## Fields

Required top-level keys:

| Key | Meaning |
| --- | --- |
| `schema_version` | String `"1.1"`; the older `1.0` contract is rejected because its EOP source label did not supply the data. |
| `tle_line1`, `tle_line2` | Original 69-character archived TLE lines; no regenerated elements or whitespace normalization. |
| `tle_source` | Nonempty, human-readable source label. The archived example retains its existing Vallado/python-sgp4 label. |
| `analysis_start_utc`, `analysis_end_utc` | Scalar UTC ISO-8601 timestamps with seconds and trailing `Z`; end must follow start. |
| `stations` | Nonempty ordered array of fixed WGS84 stations. Each needs `name`, `latitude_deg`, `longitude_deg`, `height_m`. Latitude is in `[-90,90]`, east longitude in `[-180,180]`; height is ellipsoidal metres. |
| `earth_orientation_mode` | `"configured_iers"` or `"explicit_table"`. No implicit mode selection. |
| `earth_orientation_source` | Nonempty source label recorded in the result. |

`earth_orientation_table_file` is required only for `explicit_table` and
forbidden for `configured_iers`. It is a path relative to the config file's
directory, resolved when the config is loaded rather than against the process
working directory. The loader reads the bytes once, computes their SHA-256,
validates the table and stores immutable rows in `AnalysisConfig`. The result
records the normalized relative table identity and content hash, never a
checkout-specific absolute path. A missing or malformed file raises
`InputConfigError` before scientific execution.

The explicit JSON table has exactly `mjd` (strictly increasing integer days),
`ut1_minus_utc_s` (seconds), `xp_arcsec` and `yp_arcsec` (arcseconds). Each is
an equal-length finite numeric array with at least two rows. Astropy's existing
frame service consumes these values; the loader does not implement a frame
transformation. The canonical table is clearly **test/reproducibility-only**.
It is selected only when `earth_orientation_mode` is `explicit_table`.

`configured_iers` uses the caller's normal Astropy IERS configuration, with no
table file or fixture fallback. Required EOP still fails closed as `FAILED` /
`EOP_UNAVAILABLE` under the existing MA-06 run contract.

Optional keys and established `AnalysisConfig` defaults:

| Key | Default | Units/meaning |
| --- | --- | --- |
| `minimum_elevation_deg` | `10.0` | Degrees; geometric access mask. |
| `coarse_step_s` | `5.0` | Seconds; positive event-search step. |
| `root_tolerance_s` | `0.01` | Seconds; positive entry/exit refinement tolerance. |
| `source_revision` | `null` | Nonempty externally supplied build revision, or `null`. |

Peak refinement (`0.002 s`), the 7-day TLE-age warning and the 24-hour
comparison-duration warning are fixed release settings. They remain in the
run-result provenance/configuration and are not input overrides.

Unknown, missing, duplicate or wrongly typed fields are rejected, including
unknown station keys. JSON booleans are not numbers. Nonfinite numeric values
are rejected. `TleRecord` checks both line identities and lengths, ASCII,
numeric checksum digits and checksum arithmetic, catalogue agreement, SGP4
field parsing and SGP4 initialization before a run can begin. Its parsed epoch
is a scalar UTC Astropy `Time`; the raw epoch field remains in line 1.

The archived example explicitly references
[`test_only_eop.json`](../examples/vanguard_run/test_only_eop.json). No test-side
EOP injection is needed to reproduce its saved result.
