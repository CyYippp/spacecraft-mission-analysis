"""Guard retained GMAT Phase B evidence without requiring GMAT in CI."""

import json
import math
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "validation" / "gmat" / "phase_b"


def _json(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def test_phase_b_raw_evidence_and_frozen_scripts_match_manifest() -> None:
    manifest = _json("sha256_manifest.json")
    assert manifest
    for name, expected in manifest.items():
        assert sha256((HERE / name).read_bytes()).hexdigest() == expected, name

    preparation = _json("prepared.json")
    for stage, expected in preparation["scripts_sha256"].items():
        assert sha256((HERE / f"{stage}.script").read_bytes()).hexdigest() == expected
    assert preparation["gravity_sha256"] == (
        "3e8806223250224d3c1333a010eb5c2cc5a212a56ccee4024db81b9d889db5ea"
    )


def test_phase_b_gates_and_sampled_evidence_are_retained() -> None:
    gate = _json("gate.json")
    convergence = _json("convergence.json")
    comparison = _json("state_comparison.json")
    contacts = _json("contact_comparison.json")

    assert gate["status"] == "PASS"
    assert gate["position_residual_norm_km"] <= 1e-6
    assert gate["velocity_residual_norm_km_s"] <= 1e-9
    assert convergence["status"] == "PASS"
    assert convergence["position_difference_norm_km"] <= 0.001
    assert convergence["velocity_difference_norm_km_s"] <= 1e-6
    assert comparison["status"] == "CONTINUOUS_REVIEWED"
    assert comparison["cross_model_magnitude_limit"] is None
    assert [row["offset_min"] for row in comparison["samples"]] == list(range(0, 41, 5))
    for row in comparison["samples"]:
        assert all(
            math.isfinite(value)
            for key in (
                "production_position_gcrs_km",
                "gmat_position_earthicrf_km",
                "gmat_minus_production_position_km",
                "production_velocity_gcrs_km_s",
                "gmat_velocity_earthicrf_km_s",
                "gmat_minus_production_velocity_km_s",
            )
            for value in row[key]
        )
    assert contacts["cross_model_timing_limit"] is None
    assert [
        (station["production_event_count"], station["gmat_event_count"])
        for station in contacts["stations"]
    ] == [(1, 1), (1, 1)]
