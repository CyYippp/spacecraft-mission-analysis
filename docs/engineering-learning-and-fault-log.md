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
files at this alignment. This entry records only the F-015 question supplied
for this review; it does not reconstruct an unavailable historical log.

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
