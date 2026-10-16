"""Phase A downstream comparison with a shared SGP4 propagation package."""

from datetime import datetime, timezone
from math import isfinite

import pytest
from skyfield.api import EarthSatellite, load
from validation import skyfield_phase_a as phase_a

from spacecraft_mission_analysis import Sgp4Propagator, TleRecord


@pytest.fixture(scope="module")
def report():
    # The fixed Phase A cases are the only cases executed here. The documented
    # southern-hemisphere hold-out is deliberately absent from this registry.
    assert tuple(case["name"] for case in phase_a.CASES) == (
        "A_equator_greenwich",
        "B_35N_120W",
    )
    return phase_a.characterize_phase_a()


def test_shared_kernel_tle_identity_and_matched_eop(report) -> None:
    assert report["versions"] == {
        "skyfield": "1.55",
        "sgp4": "2.27",
        "astropy": "7.2.1",
        "scipy": "1.17.1",
    }
    assert report["tle_catalog_id"] == 5
    assert report["sgp4_mu_km3_s2"] == 398600.8
    assert report["sgp4_radius_km"] == 6378.135
    assert report["max_abs_dut1_interpolation_residual_s"] < 1e-9
    assert report["polar_motion_arcsec"] == {"xp": 0.0, "yp": 0.0}


def test_exact_tle_lines_and_sgp4_epoch_split_are_shared() -> None:
    line1 = phase_a.TLE_FIXTURE["tle_line1"]
    line2 = phase_a.TLE_FIXTURE["tle_line2"]
    propagator = Sgp4Propagator(TleRecord.from_lines(line1, line2))
    skyfield = EarthSatellite(line1, line2, ts=load.timescale(builtin=True))
    assert skyfield.model.satnum == propagator.tle.catalog_id == 5
    assert type(skyfield.model) is type(propagator._satellite)
    assert (skyfield.model.jdsatepoch, skyfield.model.jdsatepochF) == (
        propagator._satellite.jdsatepoch,
        propagator._satellite.jdsatepochF,
    )


def test_fixed_development_event_counts_and_clipping(report) -> None:
    case_a, case_b = report["cases"]
    assert (case_a["production_complete_windows"], case_a["skyfield_complete_windows"]) == (
        1,
        1,
    )
    assert (case_b["production_complete_windows"], case_b["skyfield_complete_windows"]) == (
        5,
        5,
    )
    assert case_b["production_total_windows"] == 7
    assert len(case_b["production_clipped_windows"]) == 2
    assert len(case_b["skyfield_incomplete_events"]) == 2
    assert sum(pair["ordinary_for_timing"] for pair in case_b["paired_complete_windows"]) == 4
    assert report["aggregate"]["complete_window_count_agreement"]


def test_pointwise_and_opposite_event_geometry_are_recorded(report) -> None:
    for case in report["cases"]:
        assert case["pointwise_sample_count"] > 0
        assert isfinite(case["pointwise_max_abs_delta_el_deg"])
        assert isfinite(case["pointwise_rms_delta_el_deg"])
        assert all(
            isfinite(value)
            for crossing in case["near_crossings"]
            for value in crossing["delta_el_deg"].values()
            if value is not None
        )
        for pair in case["paired_complete_windows"]:
            for name in ("rise", "set"):
                event = pair[name]
                assert event["skyfield_bisection_width_s"] <= phase_a.BISECTION_WIDTH_S
                assert isfinite(event["production_minus_raw_s"])
                assert isfinite(event["production_minus_refined_s"])
                assert isfinite(event["skyfield_mask_at_production_deg"])
                assert isfinite(event["production_mask_at_skyfield_refined_deg"])


def test_missing_skyfield_sign_bracket_is_explicit(monkeypatch) -> None:
    monkeypatch.setattr(phase_a, "_skyfield_elevation", lambda *args: 9.0)
    with pytest.raises(ValueError, match="no oriented sign-change bracket"):
        phase_a._refine_skyfield_event(
            None, None, None, datetime(2000, 6, 27, tzinfo=timezone.utc), 0
        )
