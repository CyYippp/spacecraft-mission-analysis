# Engineering learning and fault log

This document is an educational and historical learning companion. Current
requirements, assumptions, engineering dispositions, verification status and
validation status are governed by the repository's authoritative
[requirements](requirements.md), [assumptions](assumptions.md),
[issues](issues.md), [decisions](decisions/README.md),
[verification](verification.md) and [validation](validation.md) records. If this
document conflicts with those records, the authoritative repository record
takes precedence.

No earlier learning/fault log was present in the repository or checked project
files at the repository-alignment increment. The F-015 entry below records only
the question supplied for that review; it does not reconstruct an unavailable
historical log. Later entries are added when new interview-relevant learning
arises from implementation.

## F-015 — zero-range look-angle geometry

**Status: Resolved by inspection of the merged implementation and tests.**

When `E = N = U = 0`, geometric range is zero and there is no viewing
direction. [enu_to_az_el_range](../src/spacecraft_mission_analysis/geometry.py)
computes the range with nested `hypot` and raises `ValueError` with
`ENU vector must have a finite nonzero range` before constructing `AzElRange`.
The parameterized
[test_zero_or_nonfinite_displacement_is_explicit_failure](../tests/test_look_angles.py)
includes `(0.0, 0.0, 0.0)` and asserts that `ValueError` is raised. The
[verification record](verification.md#enu-to-geometric-azimuth-elevation-and-range)
also records the failure-path behaviour. No production correction or open
engineering issue is required.

## Maximum elevation — numerical interpretation

This increment records no observed peak defect. Bounded scalar optimization
refines a smooth peak efficiently, but its interior result must be compared
with both ends of a clipped access window. A flat elevation plateau has no
unique peak time: the implementation returns the earliest exactly tied
candidate, while nearly flat timestamps deserve no precision claim. Existing
coarse samples expose multiple resolved peaks for separate local refinement;
they cannot prove a global maximum for an arbitrary hidden narrow feature.
The live limitation and evidence are in [ISS-006](issues.md#iss-006--peak-search-globality-boundary)
and [verification](verification.md#maximum-elevation-within-detected-access-windows).

## Run status — no pass versus failed computation

This increment found no new physical-model fault. A zero-window list is a
scientific result only after every required propagation and frame evaluation
completed. The run boundary therefore carries explicit status: successful
no-pass retains empty per-station windows and zero coverage, while failed EOP
or SGP4 processing has unavailable access/coverage fields and a structured
error. Even a first station's completed windows are discarded if a later
station fails. The archived input and frozen output schema make that distinction
reviewable without treating a 7-day warning heuristic as orbit uncertainty.
See the [run schema](run-schema-v1.md) and [fault tests](../tests/test_run.py).

## EOP acquisition — classify failure before output

The frame code checked missing EOP *after* obtaining a table; a table-acquisition
`OSError` could escape the project-specific error path. This is recorded as
[ISS-007](issues.md#iss-007--eop-acquisition-error-escaped-the-frame-boundary).
The narrow correction converts acquisition/query `OSError` or `ValueError` to
`FrameTransformError`, which the run layer maps to a structured
`EOP_UNAVAILABLE` failure. A scoped monkeypatch checks the path without
changing the user's IERS cache. The correction improves failure reporting; it
does not add synthetic EOP data or validate the resulting physical geometry.

## Cross-platform numerical output — exact bytes versus scientific meaning

[ISS-008](issues.md#iss-008--cross-platform-peak-snapshot-bytes) arose when
Ubuntu CI compared an archived Windows JSON file with a fresh run. Stable
configuration, provenance, pass boundaries and coverage matched, but the
bounded optimizer's peak elevation/time differed in last bits. Exact bytes
remain the right requirement for repeated serialization *within one
environment*. A saved file from another platform is a strict oracle for the
stable fields and a bounded numerical check for optimizer fields. This does
not authorize changing the MA-04 peak criteria or rewriting the archived
scientific result to fit CI.

## Archived TLE integrity at the input boundary

[ISS-009](issues.md#iss-009--malformed-tle-escaped-the-input-boundary) shows why
a parser's checksum helper must be checked for its exact behaviour:
`python-sgp4` verifies a numeric checksum but skips a non-digit checksum
column. The input boundary now checks that column first, validates the pair,
and retains the original 69-character lines. A malformed request raises
`InputConfigError` before `run_analysis()`, while a later propagation failure
remains a scientific `FAILED` result. Keeping those outcomes distinct makes
the archived evidence and failure provenance reviewable.
