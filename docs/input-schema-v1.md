# Analysis input contract: schema 1.0

[`load_analysis_config(path)`](../src/spacecraft_mission_analysis/input.py) reads
UTF-8 JSON into the existing `AnalysisConfig`; `parse_analysis_config(mapping)`
provides the same validation for an in-memory mapping. The canonical archived
example is [`config.json`](../examples/vanguard_run/config.json). Input schema
`1.0` and [run-result schema `1.0`](run-schema-v1.md) are separate contracts.
Malformed input raises `InputConfigError` before `run_analysis()`; it does not
produce a scientific `FAILED` result.

## Fields

Required top-level keys:

| Key | Meaning |
| --- | --- |
| `schema_version` | String `"1.0"`. |
| `tle_line1`, `tle_line2` | Original 69-character archived TLE lines; no regenerated elements or whitespace normalization. |
| `tle_source` | Nonempty, human-readable source label. The archived example retains its existing Vallado/python-sgp4 label. |
| `analysis_start_utc`, `analysis_end_utc` | Scalar UTC ISO-8601 timestamps with seconds and trailing `Z`; end must follow start. |
| `stations` | Nonempty ordered array of fixed WGS84 stations. Each needs `name`, `latitude_deg`, `longitude_deg`, `height_m`. Latitude is in `[-90,90]`, east longitude in `[-180,180]`; height is ellipsoidal metres. |
| `earth_orientation_source` | Nonempty label for the configured Astropy IERS source; the label does not select or load an IERS table. |

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

The archived example's synthetic zero-UT1/polar-motion table lives in
[`test_only_eop.json`](../examples/vanguard_run/test_only_eop.json). Tests
explicitly scope that table around the run. It is verification fixture data,
not a production config field or a production default; a normal run uses the
caller's configured Astropy IERS data and fails closed if required EOP data
cannot be obtained.
