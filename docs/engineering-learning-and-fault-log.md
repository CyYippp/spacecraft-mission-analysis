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
