"""One-time, validation-only Skyfield Phase B hold-out runner.

Run explicitly with ``python tests/validation/skyfield_phase_b.py`` from the
repository root. Normal pytest/CI never invokes this module. An existing
result file blocks a second execution.
"""

import hashlib
import inspect
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from math import isfinite, sqrt
from pathlib import Path

import astropy
import astropy.units as u
import scipy
import sgp4
import skyfield
import skyfield_phase_a as phase_a
from astropy.utils import iers
from skyfield.api import EarthSatellite, load, wgs84

from spacecraft_mission_analysis import (
    GroundStation,
    Sgp4Propagator,
    TleRecord,
    find_satellite_access_windows,
    satellite_elevation_deg,
)

UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path(__file__).with_name("phase_b_results.json")
TLE_PATH = REPO_ROOT / "tests/fixtures/access/vanguard_greenwich.json"
PHASE_A_PATH = Path(__file__).with_name("phase_a_results.json")
DECISION_PATH = REPO_ROOT / "docs/decisions/0002-skyfield-holdout-acceptance.md"
EXPECTED_TLE_FIXTURE_SHA256 = "40382ec8a43d7f5e410de127103d1faed9fd35d5e0d4ad0a496ab799bde087bb"
EXPECTED_PHASE_A_SHA256 = "7472063e8ae304dc10948a712cabdebdf2d570753f08c09884cf5b35914fb3a4"

CASE = {
    "name": "Phase_B_Sydney_area_holdout",
    "station": {
        "name": "Synthetic WGS84 southern hold-out station",
        "latitude_deg": -33.5,
        "longitude_deg": 151.2,
        "height_m": 100.0,
    },
    "start": "2000-06-28T00:00:00+00:00",
    "end": "2000-06-29T00:00:00+00:00",
    "point_step_s": 300,
}
MAX_REFINED_EVENT_TIME_DIFF_S = 0.020
MAX_POINTWISE_ELEVATION_DIFF_DEG = 1e-9
ORDINARY_CULMINATION_MIN_DEG = 15.0
MAX_DUT1_MISMATCH_S = 1e-11
EXPECTED_VALIDATION_VERSIONS = {
    "skyfield": "1.55",
    "sgp4": "2.27",
    "astropy": "7.2.1",
    "scipy": "1.17.1",
}


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@contextmanager
def _matched_holdout_eop(ts):
    """Use Phase A's EOP convention, with June 30 supporting the exact end."""
    dates = [datetime(2000, 6, day, tzinfo=UTC) for day in (26, 27, 28, 29, 30)]
    dut1_s = [float(phase_a._skyfield_time(ts, day).dut1) for day in dates]
    table = iers.IERS(
        {
            "MJD": [float(phase_a._astropy_time(day).mjd) for day in dates] * u.day,
            "UT1_UTC": dut1_s * u.s,
            "PM_x": [0.0] * len(dates) * u.arcsec,
            "PM_y": [0.0] * len(dates) * u.arcsec,
        }
    )
    with iers.conf.set_temp("auto_download", False), iers.earth_orientation_table.set(table):
        yield {day.isoformat(): dut1 for day, dut1 in zip(dates, dut1_s, strict=True)}


def _preflight() -> tuple[str, str, str]:
    if OUTPUT.exists():
        raise FileExistsError(f"first-observed result already exists: {OUTPUT}")
    if _git("branch", "--show-current") != "feat/skyfield-holdout":
        raise RuntimeError("run only from the dedicated Phase B branch")
    if _git("status", "--porcelain"):
        raise RuntimeError("commit the runner and clean the worktree before execution")
    fixture_hash, phase_a_hash = _sha256(TLE_PATH), _sha256(PHASE_A_PATH)
    if fixture_hash != EXPECTED_TLE_FIXTURE_SHA256:
        raise RuntimeError("archived TLE fixture changed")
    if phase_a_hash != EXPECTED_PHASE_A_SHA256:
        raise RuntimeError("Phase A result artifact changed")
    if not DECISION_PATH.is_file():
        raise RuntimeError("frozen Decision 0002 is missing")
    if (phase_a.MASK_DEG, phase_a.BISECTION_WIDTH_S) != (10.0, 0.001):
        raise RuntimeError("Phase A validation mask or bisection method changed")
    production_parameters = inspect.signature(find_satellite_access_windows).parameters
    if (
        production_parameters["coarse_step_s"].default,
        production_parameters["root_tolerance_s"].default,
    ) != (5.0, 0.01):
        raise RuntimeError("production access numerical defaults changed")
    return _git("rev-parse", "HEAD"), fixture_hash, phase_a_hash


def _checkpoint(result: dict, *, first: bool = False) -> None:
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if first:
        with OUTPUT.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
        return
    pending = OUTPUT.with_suffix(".json.pending")
    with pending.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
    os.replace(pending, OUTPUT)


def _skyfield_accesses(
    events: list[dict], start: datetime, end: datetime
) -> tuple[list[dict], list[str]]:
    """Build access intervals from refined crossings, preserving clipped ends."""
    crossings = [event for event in events if event["code"] in (0, 2)]
    active = (
        {"start": start, "rise": None, "culminations": []}
        if crossings and crossings[0]["code"] == 2
        else None
    )
    accesses, anomalies = [], []
    for event in events:
        if event["code"] == 1:
            if active is not None:
                active["culminations"].append(event)
        elif event["code"] == 0:
            if active is not None:
                anomalies.append(f"rise without prior set at raw event {event['index']}")
            active = {
                "start": event["refined"]["time"],
                "rise": event,
                "culminations": [],
            }
        elif event["code"] == 2:
            if active is None:
                anomalies.append(f"set without prior rise at raw event {event['index']}")
                continue
            active["end"] = event["refined"]["time"]
            active["set"] = event
            accesses.append(active)
            active = None
    if active is not None:
        active["end"] = end
        active["set"] = None
        accesses.append(active)
    for index, access in enumerate(accesses):
        access["index"] = index
        complete = access["rise"] is not None and access["set"] is not None
        if not complete:
            access["classification"] = "boundary_clipped"
        elif not access["culminations"]:
            access["classification"] = "unclassified"
            anomalies.append(f"complete Skyfield access {index} has no culmination")
        else:
            peak = max(event["culmination_elevation_deg"] for event in access["culminations"])
            access["classification"] = (
                "ordinary"
                if peak >= ORDINARY_CULMINATION_MIN_DEG
                else "near_threshold"
                if phase_a.MASK_DEG < peak < ORDINARY_CULMINATION_MIN_DEG
                else "grazing_or_unclassified"
            )
        access["culmination_deg"] = (
            max(event["culmination_elevation_deg"] for event in access["culminations"])
            if access["culminations"]
            else None
        )
    return accesses, anomalies


def _production_accesses(windows) -> tuple[list[dict], list[dict]]:
    accesses, crossings = [], []
    for index, window in enumerate(windows):
        start, end = phase_a._utc_datetime(window.start), phase_a._utc_datetime(window.end)
        access = {
            "index": index,
            "start": start,
            "end": end,
            "window": window,
            "start_clipped": window.start_clipped,
            "end_clipped": window.end_clipped,
        }
        accesses.append(access)
        if not window.start_clipped:
            crossings.append({"type": "rise", "time": start, "access_index": index})
        if not window.end_clipped:
            crossings.append({"type": "set", "time": end, "access_index": index})
    return accesses, sorted(crossings, key=lambda event: event["time"])


def _corresponding_accesses(production: list[dict], reference: list[dict]) -> list[tuple[int, int]]:
    """Pair only mutually unique overlapping access intervals."""
    p_candidates = {
        p["index"]: [
            s["index"] for s in reference if max(p["start"], s["start"]) < min(p["end"], s["end"])
        ]
        for p in production
    }
    s_candidates = {
        s["index"]: [
            p["index"] for p in production if max(p["start"], s["start"]) < min(p["end"], s["end"])
        ]
        for s in reference
    }
    return [
        (p_index, candidates[0])
        for p_index, candidates in p_candidates.items()
        if len(candidates) == 1 and s_candidates[candidates[0]] == [p_index]
    ]


def _record_skyfield_access(access: dict) -> dict:
    return {
        "index": access["index"],
        "start_utc": access["start"].isoformat(),
        "end_utc": access["end"].isoformat(),
        "start_clipped": access["rise"] is None,
        "end_clipped": access["set"] is None,
        "rise_event_index": access["rise"]["index"] if access["rise"] else None,
        "set_event_index": access["set"]["index"] if access["set"] else None,
        "culmination_deg": access["culmination_deg"],
        "classification": access["classification"],
    }


def _record_production_access(access: dict) -> dict:
    return {
        "index": access["index"],
        "start_utc": access["start"].isoformat(),
        "end_utc": access["end"].isoformat(),
        "duration_s": access["window"].duration_s,
        "start_clipped": access["start_clipped"],
        "end_clipped": access["end_clipped"],
    }


def _event_pair(
    production: dict, reference: dict, kind: str, propagator, station, ts, satellite, site
) -> dict:
    sf_event = reference["rise"] if kind == "rise" else reference["set"]
    prod_time = production["window"].start if kind == "rise" else production["window"].end
    raw, refined = sf_event["raw_time"], sf_event["refined"]["time"]
    return {
        "type": kind,
        "production_access_index": production["index"],
        "skyfield_access_index": reference["index"],
        "skyfield_event_index": sf_event["index"],
        "culmination_deg": reference["culmination_deg"],
        "classification": reference["classification"],
        "production_utc": phase_a._utc_datetime(prod_time).isoformat(),
        "skyfield_raw_utc": raw.isoformat(),
        "skyfield_bisected_utc": refined.isoformat(),
        "production_minus_raw_s": phase_a._seconds_between(prod_time, raw),
        "production_minus_bisected_s": phase_a._seconds_between(prod_time, refined),
        "skyfield_elevation_minus_mask_at_production_deg": phase_a._skyfield_elevation(
            ts, satellite, site, phase_a._utc_datetime(prod_time)
        )
        - phase_a.MASK_DEG,
        "production_elevation_minus_mask_at_bisected_deg": satellite_elevation_deg(
            propagator, station, phase_a._astropy_time(refined)
        )
        - phase_a.MASK_DEG,
    }


def _evaluate(result: dict) -> None:
    production = result["production_genuine_crossings"]
    skyfield_events = result["skyfield_genuine_crossings"]
    paired = result["paired_events"]
    p_rises = sum(event["type"] == "rise" for event in production)
    p_sets = sum(event["type"] == "set" for event in production)
    s_rises = sum(event["type"] == "rise" for event in skyfield_events)
    s_sets = sum(event["type"] == "set" for event in skyfield_events)
    same_counts = (p_rises, p_sets) == (s_rises, s_sets)
    same_order = [event["type"] for event in production] == [
        event["type"] for event in skyfield_events
    ]
    paired_p = {(event["production_access_index"], event["type"]) for event in paired}
    paired_s = {event["skyfield_event_index"] for event in paired}
    actual_p = {(event["access_index"], event["type"]) for event in production}
    actual_s = {event["event_index"] for event in skyfield_events}
    all_correspond = (
        paired_p == actual_p and paired_s == actual_s and not result["skyfield_sequence_anomalies"]
    )
    event_status = "PASS" if same_counts and same_order and all_correspond else "FAIL"

    ordinary = [
        event["production_minus_bisected_s"]
        for event in paired
        if event["classification"] == "ordinary"
    ]
    if ordinary:
        timing_status = (
            "PASS"
            if all(abs(value) <= MAX_REFINED_EVENT_TIME_DIFF_S for value in ordinary)
            else "FAIL"
        )
        timing_max = max(abs(value) for value in ordinary)
        timing_rms = sqrt(sum(value * value for value in ordinary) / len(ordinary))
    else:
        timing_status, timing_max, timing_rms = "NOT EXERCISED", None, None

    samples = result["pointwise_samples"]
    if samples:
        largest = max(samples, key=lambda sample: abs(sample["delta_el_deg"]))
        pointwise_max = abs(largest["delta_el_deg"])
        pointwise_rms = sqrt(sum(sample["delta_el_deg"] ** 2 for sample in samples) / len(samples))
        pointwise_status = "PASS" if pointwise_max <= MAX_POINTWISE_ELEVATION_DIFF_DEG else "FAIL"
        max_time = largest["time_utc"]
    else:
        pointwise_status, pointwise_max, pointwise_rms, max_time = (
            "NOT EXERCISED",
            None,
            None,
            None,
        )

    statuses = (event_status, timing_status, pointwise_status)
    overall = (
        "FAIL — investigation required"
        if "FAIL" in statuses
        else "INCONCLUSIVE"
        if "NOT EXERCISED" in statuses
        else "PASS"
    )
    result["evaluation"] = {
        "event_sequence": {
            "status": event_status,
            "production_rises": p_rises,
            "production_sets": p_sets,
            "skyfield_rises": s_rises,
            "skyfield_sets": s_sets,
            "same_chronological_order": same_order,
            "all_genuine_crossings_correspond": all_correspond,
        },
        "ordinary_refined_timing": {
            "status": timing_status,
            "event_count": len(ordinary),
            "max_abs_diff_s": timing_max,
            "rms_diff_s": timing_rms,
            "limit_s": MAX_REFINED_EVENT_TIME_DIFF_S,
        },
        "pointwise_elevation": {
            "status": pointwise_status,
            "sample_count": len(samples),
            "max_abs_delta_el_deg": pointwise_max,
            "rms_delta_el_deg": pointwise_rms,
            "max_time_utc": max_time,
            "limit_deg": MAX_POINTWISE_ELEVATION_DIFF_DEG,
        },
        "overall_disposition": overall,
    }


def main() -> None:
    source_commit, fixture_hash, phase_a_hash = _preflight()
    versions = {
        "skyfield": skyfield.__version__,
        "sgp4": sgp4.__version__,
        "astropy": astropy.__version__,
        "scipy": scipy.__version__,
    }
    if versions != EXPECTED_VALIDATION_VERSIONS:
        raise RuntimeError(f"validation package versions differ from Phase A: {versions}")
    start, end = (datetime.fromisoformat(CASE[key]) for key in ("start", "end"))
    ts = load.timescale(builtin=True)
    line1, line2 = phase_a.TLE_FIXTURE["tle_line1"], phase_a.TLE_FIXTURE["tle_line2"]
    tle = TleRecord.from_lines(line1, line2, source=phase_a.TLE_FIXTURE["tle_provenance"])
    propagator = Sgp4Propagator(tle)
    satellite = EarthSatellite(line1, line2, ts=ts)
    if satellite.model.satnum != tle.catalog_id or (
        satellite.model.jdsatepoch,
        satellite.model.jdsatepochF,
    ) != (
        propagator._satellite.jdsatepoch,
        propagator._satellite.jdsatepochF,
    ):
        raise RuntimeError("Skyfield and production SGP4 TLE identity differs")
    if (satellite.model.mu, satellite.model.radiusearthkm) != (
        propagator._satellite.mu,
        propagator._satellite.radiusearthkm,
    ):
        raise RuntimeError("Skyfield and production SGP4 gravity constants differ")
    station = GroundStation(**CASE["station"])
    site = wgs84.latlon(station.latitude_deg, station.longitude_deg, elevation_m=station.height_m)

    with _matched_holdout_eop(ts) as dut1_by_day:
        check_times = (start, start + timedelta(hours=12, minutes=34, seconds=56.789), end)
        dut1_checks = [
            {
                "time_utc": when.isoformat(),
                "astropy_minus_skyfield_s": float(
                    phase_a._astropy_time(when).delta_ut1_utc
                    - phase_a._skyfield_time(ts, when).dut1
                ),
            }
            for when in check_times
        ]
        dut1_max = max(abs(item["astropy_minus_skyfield_s"]) for item in dut1_checks)
        if dut1_max > MAX_DUT1_MISMATCH_S:
            raise RuntimeError(f"DUT1 matching exceeds {MAX_DUT1_MISMATCH_S} s: {dut1_max} s")

        result = {
            "schema": "skyfield-phase-b-first-observed-v1",
            "execution_started_utc": datetime.now(UTC).isoformat(),
            "execution_status": "RUNNING",
            "stage": "initialized",
            "source_commit": source_commit,
            "source_branch": "feat/skyfield-holdout",
            "fixture_sha256": fixture_hash,
            "phase_a_results_sha256": phase_a_hash,
            "decision_0002_sha256": _sha256(DECISION_PATH),
            "fixture": {
                "tle_line1": line1,
                "tle_line2": line2,
                "tle_provenance": phase_a.TLE_FIXTURE["tle_provenance"],
                "station": CASE["station"],
                "start_utc": start.isoformat(),
                "end_utc": end.isoformat(),
                "mask_deg": phase_a.MASK_DEG,
            },
            "versions": {
                "python": sys.version.split()[0],
                **versions,
            },
            "conventions": {
                "shared_sgp4_kernel": True,
                "skyfield_timescale": "bundled builtin",
                "astropy_iers": "scoped offline table with Skyfield daily DUT1",
                "polar_motion_arcsec": {"xp": 0.0, "yp": 0.0},
                "refraction": False,
                "production_coarse_step_s": 5.0,
                "production_root_tolerance_s": 0.01,
                "skyfield_bisection_width_s": phase_a.BISECTION_WIDTH_S,
            },
            "acceptance": {
                "ordinary_culmination_min_deg": ORDINARY_CULMINATION_MIN_DEG,
                "max_refined_event_time_diff_s": MAX_REFINED_EVENT_TIME_DIFF_S,
                "max_pointwise_elevation_diff_deg": MAX_POINTWISE_ELEVATION_DIFF_DEG,
                "pointwise_sampling": "300 s grid including bounds; Skyfield bisected genuine rise/set at -30, 0, +30 s inside interval; deduplicate",
                "raw_find_events_timing": "diagnostic only",
            },
            "eop": {
                "daily_dut1_s": dut1_by_day,
                "dut1_checks": dut1_checks,
                "max_abs_dut1_mismatch_s": dut1_max,
                "matching_limit_s": MAX_DUT1_MISMATCH_S,
            },
        }
        _checkpoint(result, first=True)
        try:
            raw_times, codes = satellite.find_events(
                site,
                phase_a._skyfield_time(ts, start),
                phase_a._skyfield_time(ts, end),
                altitude_degrees=phase_a.MASK_DEG,
            )
            sf_events = [
                {"index": index, "code": int(code), "raw_time": time.utc_datetime()}
                for index, (time, code) in enumerate(zip(raw_times, codes, strict=True))
            ]
            result["skyfield_events"] = [
                {
                    "index": event["index"],
                    "code": event["code"],
                    "raw_utc": event["raw_time"].isoformat(),
                }
                for event in sf_events
            ]
            result["stage"] = "raw_skyfield_events_saved"
            _checkpoint(result)

            for event, recorded in zip(sf_events, result["skyfield_events"], strict=True):
                if event["code"] == 1:
                    peak = phase_a._skyfield_elevation(ts, satellite, site, event["raw_time"])
                    event["culmination_elevation_deg"] = peak
                    recorded["culmination_elevation_deg"] = peak
                else:
                    refined = phase_a._refine_skyfield_event(
                        ts, satellite, site, event["raw_time"], event["code"]
                    )
                    event["refined"] = refined
                    recorded["bisected_utc"] = refined["time"].isoformat()
                    recorded["bisection_width_s"] = refined["final_width_s"]
                    recorded["bisection_mask_residual_deg"] = refined["mask_residual_deg"]
                    recorded["initial_bracket_half_width_s"] = refined["bracket_half_width_s"]
                result["stage"] = f"skyfield_event_{event['index']}_processed"
                _checkpoint(result)

            sf_accesses, anomalies = _skyfield_accesses(sf_events, start, end)
            result["skyfield_accesses"] = [_record_skyfield_access(item) for item in sf_accesses]
            result["skyfield_sequence_anomalies"] = anomalies
            result["skyfield_genuine_crossings"] = [
                {
                    "event_index": event["index"],
                    "type": "rise" if event["code"] == 0 else "set",
                    "time_utc": event["refined"]["time"].isoformat(),
                }
                for event in sf_events
                if event["code"] in (0, 2) and start <= event["refined"]["time"] <= end
            ]
            result["stage"] = "skyfield_accesses_saved"
            _checkpoint(result)

            windows = find_satellite_access_windows(
                propagator, station, phase_a._astropy_time(start), phase_a._astropy_time(end)
            )
            production, p_crossings = _production_accesses(windows)
            result["production_accesses"] = [_record_production_access(item) for item in production]
            result["production_genuine_crossings"] = [
                {
                    "type": item["type"],
                    "time_utc": item["time"].isoformat(),
                    "access_index": item["access_index"],
                }
                for item in p_crossings
            ]
            result["stage"] = "production_accesses_saved"
            _checkpoint(result)

            access_pairs = _corresponding_accesses(production, sf_accesses)
            result["corresponding_accesses"] = [
                {"production_access_index": p, "skyfield_access_index": s} for p, s in access_pairs
            ]
            result["paired_events"] = []
            for p_index, s_index in access_pairs:
                p, s = production[p_index], sf_accesses[s_index]
                for kind in ("rise", "set"):
                    if (kind == "rise" and p["start_clipped"]) or (
                        kind == "set" and p["end_clipped"]
                    ):
                        continue
                    if s[kind] is None:
                        continue
                    pair = _event_pair(p, s, kind, propagator, station, ts, satellite, site)
                    result["paired_events"].append(pair)
                    result["stage"] = f"paired_event_{len(result['paired_events'])}_saved"
                    _checkpoint(result)

            matched_skyfield_accesses = {s for _, s in access_pairs}
            result["near_threshold_diagnostics"] = [
                {
                    "skyfield_access_index": access["index"],
                    "culmination_deg": access["culmination_deg"],
                    "skyfield_detected": True,
                    "production_detected": any(
                        max(p["start"], access["start"]) < min(p["end"], access["end"])
                        for p in production
                    ),
                    "uniquely_paired": access["index"] in matched_skyfield_accesses,
                    "paired_event_indices": [
                        index
                        for index, pair in enumerate(result["paired_events"])
                        if pair["skyfield_access_index"] == access["index"]
                    ],
                }
                for access in sf_accesses
                if access["classification"] == "near_threshold"
            ]
            result["stage"] = "event_pairing_saved"
            _checkpoint(result)

            result["pointwise_samples"] = []
            genuine_sample_events = [
                event
                for event in sf_events
                if event["code"] == 1 or start <= event["refined"]["time"] <= end
            ]
            for when in phase_a._pointwise_samples(CASE, genuine_sample_events):
                production_el = satellite_elevation_deg(
                    propagator, station, phase_a._astropy_time(when)
                )
                skyfield_el = phase_a._skyfield_elevation(ts, satellite, site, when)
                if not (isfinite(production_el) and isfinite(skyfield_el)):
                    raise ValueError(f"non-finite pointwise elevation at {when.isoformat()}")
                result["pointwise_samples"].append(
                    {
                        "time_utc": when.isoformat(),
                        "production_el_deg": production_el,
                        "skyfield_el_deg": skyfield_el,
                        "delta_el_deg": production_el - skyfield_el,
                    }
                )
                result["stage"] = f"pointwise_sample_{len(result['pointwise_samples'])}_saved"
                _checkpoint(result)

            _evaluate(result)
            result["execution_status"] = "COMPLETE"
            result["execution_finished_utc"] = datetime.now(UTC).isoformat()
            result["stage"] = "evaluation_saved"
            _checkpoint(result)
        except BaseException as exc:
            result["execution_status"] = "ERROR_PARTIAL"
            result["error"] = {"type": type(exc).__name__, "message": str(exc)}
            result["execution_finished_utc"] = datetime.now(UTC).isoformat()
            _checkpoint(result)
            raise

    print(f"First-observed result: {OUTPUT}")
    print(f"SHA-256: {_sha256(OUTPUT)}")
    print(f"Disposition: {result['evaluation']['overall_disposition']}")


if __name__ == "__main__":
    main()
