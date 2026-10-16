"""Check the saved first Phase B observation without re-executing the hold-out."""

import hashlib
import json
from datetime import datetime, timedelta
from math import isclose, sqrt
from pathlib import Path

import pytest

ARTIFACT = Path(__file__).parent / "validation" / "phase_b_results.json"
FIRST_OBSERVED_SHA256 = "a521e8e859e2b799f1ead7b5b295ba1ff4afacac0c24ec1530a24e9bc3b20fc6"
SOURCE_COMMIT = "fdaa2002b733dbc937312aa558d74bfaeec11000"
FIXTURE_SHA256 = "40382ec8a43d7f5e410de127103d1faed9fd35d5e0d4ad0a496ab799bde087bb"
PHASE_A_SHA256 = "7472063e8ae304dc10948a712cabdebdf2d570753f08c09884cf5b35914fb3a4"


@pytest.fixture(scope="module")
def observed():
    data = ARTIFACT.read_bytes()
    assert hashlib.sha256(data).hexdigest() == FIRST_OBSERVED_SHA256
    return json.loads(data)


def test_first_observation_and_matched_inputs(observed) -> None:
    assert observed["execution_status"] == "COMPLETE"
    assert observed["source_commit"] == SOURCE_COMMIT
    assert observed["fixture_sha256"] == FIXTURE_SHA256
    assert observed["phase_a_results_sha256"] == PHASE_A_SHA256
    assert observed["fixture"]["station"]["latitude_deg"] == -33.5
    assert observed["fixture"]["station"]["longitude_deg"] == 151.2
    assert observed["fixture"]["station"]["height_m"] == 100.0
    assert observed["fixture"]["mask_deg"] == 10.0
    assert observed["versions"]["skyfield"] == "1.55"
    assert observed["versions"]["sgp4"] == "2.27"
    assert observed["conventions"]["polar_motion_arcsec"] == {"xp": 0.0, "yp": 0.0}
    assert observed["eop"]["max_abs_dut1_mismatch_s"] <= 1e-11


def test_genuine_crossings_and_physical_pairing(observed) -> None:
    production = observed["production_genuine_crossings"]
    skyfield = observed["skyfield_genuine_crossings"]
    assert [item["type"] for item in production] == [item["type"] for item in skyfield]
    assert [item["type"] for item in production] == ["rise", "set"] * 5
    assert all(
        not item["start_clipped"] and not item["end_clipped"]
        for item in observed["production_accesses"]
    )
    assert len(observed["production_accesses"]) == len(observed["skyfield_accesses"]) == 5

    matched = observed["corresponding_accesses"]
    assert len(matched) == 5
    assert len({item["production_access_index"] for item in matched}) == 5
    assert len({item["skyfield_access_index"] for item in matched}) == 5
    for pair in matched:
        p = observed["production_accesses"][pair["production_access_index"]]
        s = observed["skyfield_accesses"][pair["skyfield_access_index"]]
        assert max(p["start_utc"], s["start_utc"]) < min(p["end_utc"], s["end_utc"])

    status = observed["evaluation"]["event_sequence"]
    assert status["status"] == "PASS"
    assert (status["production_rises"], status["production_sets"]) == (5, 5)
    assert (status["skyfield_rises"], status["skyfield_sets"]) == (5, 5)
    assert status["all_genuine_crossings_correspond"]


def test_frozen_refined_timing_and_near_threshold_classification(observed) -> None:
    pairs = observed["paired_events"]
    ordinary = [item for item in pairs if item["classification"] == "ordinary"]
    near = [item for item in pairs if item["classification"] == "near_threshold"]
    assert (len(pairs), len(ordinary), len(near)) == (10, 8, 2)
    for item in pairs:
        production = datetime.fromisoformat(item["production_utc"])
        bisected = datetime.fromisoformat(item["skyfield_bisected_utc"])
        raw = datetime.fromisoformat(item["skyfield_raw_utc"])
        assert isclose(
            item["production_minus_bisected_s"],
            (production - bisected).total_seconds(),
            abs_tol=1e-6,
        )
        assert isclose(
            item["production_minus_raw_s"],
            (production - raw).total_seconds(),
            abs_tol=1e-6,
        )

    values = [item["production_minus_bisected_s"] for item in ordinary]
    aggregate = observed["evaluation"]["ordinary_refined_timing"]
    assert aggregate["limit_s"] == 0.020
    assert aggregate["event_count"] == len(values) == 8
    assert isclose(aggregate["max_abs_diff_s"], max(map(abs, values)), abs_tol=1e-15)
    assert isclose(
        aggregate["rms_diff_s"], sqrt(sum(v * v for v in values) / len(values)), abs_tol=1e-15
    )
    assert all(abs(value) <= 0.020 for value in values)
    assert aggregate["status"] == "PASS"

    diagnostics = observed["near_threshold_diagnostics"]
    assert len(diagnostics) == 1
    assert 10.0 < diagnostics[0]["culmination_deg"] < 15.0
    assert diagnostics[0]["skyfield_detected"] and diagnostics[0]["production_detected"]
    assert diagnostics[0]["uniquely_paired"]
    assert len(diagnostics[0]["paired_event_indices"]) == 2


def test_frozen_pointwise_set_and_elevation_limit(observed) -> None:
    fixture = observed["fixture"]
    start = datetime.fromisoformat(fixture["start_utc"])
    end = datetime.fromisoformat(fixture["end_utc"])
    expected = {start + timedelta(seconds=step) for step in range(0, 86401, 300)}
    assert max(expected) == end
    for event in observed["skyfield_events"]:
        if event["code"] in (0, 2):
            crossing = datetime.fromisoformat(event["bisected_utc"])
            if start <= crossing <= end:
                expected.update(
                    when
                    for offset in (-30, 0, 30)
                    if start <= (when := crossing + timedelta(seconds=offset)) <= end
                )

    samples = observed["pointwise_samples"]
    actual = [datetime.fromisoformat(item["time_utc"]) for item in samples]
    assert actual == sorted(expected)
    residuals = [item["delta_el_deg"] for item in samples]
    for item in samples:
        assert isclose(
            item["delta_el_deg"],
            item["production_el_deg"] - item["skyfield_el_deg"],
            abs_tol=1e-15,
        )
    aggregate = observed["evaluation"]["pointwise_elevation"]
    assert aggregate["sample_count"] == len(samples) == 319
    assert aggregate["limit_deg"] == 1e-9
    assert isclose(aggregate["max_abs_delta_el_deg"], max(map(abs, residuals)), abs_tol=1e-18)
    assert isclose(
        aggregate["rms_delta_el_deg"],
        sqrt(sum(value * value for value in residuals) / len(residuals)),
        abs_tol=1e-18,
    )
    assert aggregate["max_abs_delta_el_deg"] <= 1e-9
    assert aggregate["status"] == "PASS"
    assert observed["evaluation"]["overall_disposition"] == "PASS"
