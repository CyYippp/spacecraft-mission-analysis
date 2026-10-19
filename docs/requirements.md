# Live requirements status

The external `01-spacecraft-mission-analysis.md` portfolio plan sets scope and
intent. This repository records current implementation and evidence. Status here
is current as of the Phase B hold-out; detailed criteria and residuals remain in
[verification](verification.md) and [validation](validation.md). `IN PROGRESS`
means some required behaviour or evidence is still missing. `PARTIALLY VALIDATED`
means bounded comparison evidence exists but the full requirement remains open.

| ID | Status | Implementation / evidence | Remaining disposition |
| --- | --- | --- | --- |
| MA-01 — archived TLE input and provenance | IN PROGRESS | [TleRecord](../src/spacecraft_mission_analysis/orbit.py) preserves exact lines, UTC epoch, catalogue ID and optional source; [orbit tests](../tests/test_orbit.py) cover parsing and rejection. | Run-level input manifest and source history are not implemented. |
| MA-02 — SGP4 propagation | IN PROGRESS | [Sgp4Propagator and typed TEME state](../src/spacecraft_mission_analysis/orbit.py) use WGS72 and explicit errors; the [reference-vector verification](verification.md#reference-vector) passes. | Run-level time-since-epoch reporting is not implemented; same-model verification does not establish orbit truth. |
| MA-03 — frames and topocentric geometry | PARTIALLY VALIDATED | [Frame](../src/spacecraft_mission_analysis/frames.py), [station](../src/spacecraft_mission_analysis/stations.py), and [geometry](../src/spacecraft_mission_analysis/geometry.py) modules implement TEME→ITRS→station-relative ITRS→ENU→azimuth/elevation/range. Component [verification](verification.md) passes, including the matched split-UT1 frame reference; downstream geometry passed the [Skyfield Phase B comparison](validation.md#phase-b-first-observed-hold-out-result--pass). | The printed Appendix C discrepancy remains recorded under [ISS-001](issues.md#iss-001--vallado-printed-vector-versus-split-ut1); the shared SGP4 comparison is bounded, not physical geometry accuracy. |
| MA-04 — access events, duration, maximum elevation | IN PROGRESS | [Access solver](../src/spacecraft_mission_analysis/access.py) returns refined entry/exit windows and duration; [analytic tests](../tests/test_access.py), [integration test](../tests/test_access_integration.py), and the [Phase B hold-out](validation.md#phase-b-first-observed-hold-out-result--pass) support the implemented boundary. | Maximum elevation is not implemented; finite sampling can miss narrow near-grazing access ([ISS-002](issues.md#iss-002--finite-coarse-step-detection)). |
| MA-05 — versioned outputs and provenance | NOT STARTED | Test fixtures and validation JSON are evidence artifacts, not product outputs. | Define and implement versioned CSV/JSON with units, UTC, configuration, warnings and provenance. |
| MA-06 — warnings and failures | IN PROGRESS | [Propagation errors](../src/spacecraft_mission_analysis/orbit.py) prevent state return; [frame service](../src/spacecraft_mission_analysis/frames.py) rejects unavailable EOP and warns on predicted EOP, with [tests](../tests/test_frames.py). | Stale-TLE and unsupported-interval policies/warnings remain undefined and unimplemented. |
| MA-07 — independent comparison | PARTIALLY VALIDATED | Independent matched split-UT1 frame equations pass [verification](verification.md#active-matched-split-ut1-production-acceptance); Skyfield Phase A and frozen Phase B pass bounded downstream [validation](validation.md). | Skyfield shares `sgp4==2.27` ([ISS-003](issues.md#iss-003--shared-sgp4-validation-boundary)); independent propagation and GMAT comparisons remain future work. |
| MA-08 — temporal station coverage | NOT STARTED | No coverage or no-access-gap implementation or verification claim. | Develop only after access-interval evidence supports it. |

The [assumptions](assumptions.md), [issue register](issues.md), and
[decisions](decisions/README.md) govern the stated limitations and dispositions.
