"""Reproducible Phase A Skyfield comparison; no production imports of Skyfield."""

import json
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from math import isfinite, sqrt
from pathlib import Path

import astropy.units as u
from astropy.time import Time
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
MASK_DEG = 10.0
ORDINARY_CULMINATION_MIN_DEG = 15.0  # Selection rule, not a timing tolerance.
BISECTION_WIDTH_S = 0.001
BRACKET_HALF_WIDTHS_S = (5, 10, 20, 40, 80)
TLE_FIXTURE = json.loads(
    (Path(__file__).parents[1] / "fixtures" / "access" / "vanguard_greenwich.json").read_text(
        encoding="utf-8"
    )
)
CASES = (
    {
        "name": "A_equator_greenwich",
        "station": TLE_FIXTURE["station"],
        "start": "2000-06-27T20:00:00+00:00",
        "end": "2000-06-27T20:40:00+00:00",
        "point_step_s": 60,
    },
    {
        "name": "B_35N_120W",
        "station": {
            "name": "Synthetic WGS84 35N 120W station",
            "latitude_deg": 35.0,
            "longitude_deg": -120.0,
            "height_m": 250.0,
        },
        "start": "2000-06-27T00:00:00+00:00",
        "end": "2000-06-28T00:00:00+00:00",
        "point_step_s": 300,
    },
)


def _astropy_time(when: datetime) -> Time:
    return Time(when, scale="utc")


def _skyfield_time(ts, when: datetime):
    return ts.from_datetime(when)


def _utc_datetime(time: Time) -> datetime:
    return time.to_datetime(timezone=UTC)


def _seconds_between(first: Time, second: datetime) -> float:
    return float((first - _astropy_time(second)).to_value(u.s))


@contextmanager
def _matched_eop(ts):
    """Supply Skyfield's bundled daily DUT1 to Astropy with zero xp/yp."""
    days = (26, 27, 28, 29)  # One day of interpolation support beyond case B.
    dates = [datetime(2000, 6, day, tzinfo=UTC) for day in days]
    dut1_s = [float(_skyfield_time(ts, day).dut1) for day in dates]
    table = iers.IERS(
        {
            "MJD": [float(_astropy_time(day).mjd) for day in dates] * u.day,
            "UT1_UTC": dut1_s * u.s,
            "PM_x": [0.0] * len(days) * u.arcsec,
            "PM_y": [0.0] * len(days) * u.arcsec,
        }
    )
    with iers.conf.set_temp("auto_download", False), iers.earth_orientation_table.set(table):
        yield {day.isoformat(): dut1 for day, dut1 in zip(dates, dut1_s, strict=True)}


def _skyfield_elevation(ts, satellite, site, when: datetime) -> float:
    return float((satellite - site).at(_skyfield_time(ts, when)).altaz()[0].degrees)


def _refine_skyfield_event(ts, satellite, site, raw_time: datetime, code: int) -> dict:
    """Validation-only sign bracket and plain bisection around one rise/set."""

    def residual(when: datetime) -> float:
        return _skyfield_elevation(ts, satellite, site, when) - MASK_DEG

    bracket = None
    for half_width in BRACKET_HALF_WIDTHS_S:
        left = raw_time - timedelta(seconds=half_width)
        right = raw_time + timedelta(seconds=half_width)
        f_left, f_right = residual(left), residual(right)
        if (f_left < 0 < f_right and code == 0) or (f_left > 0 > f_right and code == 2):
            bracket = left, right, f_left, f_right, half_width
            break
    if bracket is None:
        raise ValueError(f"no oriented sign-change bracket for event {code} at {raw_time}")

    left, right, f_left, _, half_width = bracket
    while (right - left).total_seconds() > BISECTION_WIDTH_S:
        midpoint = left + (right - left) / 2
        f_mid = residual(midpoint)
        if f_mid == 0:
            left = right = midpoint
            break
        if (f_mid > 0) == (f_left > 0):
            left, f_left = midpoint, f_mid
        else:
            right = midpoint
    refined = left + (right - left) / 2
    return {
        "time": refined,
        "bracket_half_width_s": half_width,
        "final_width_s": (right - left).total_seconds(),
        "mask_residual_deg": residual(refined),
    }


def _skyfield_events(ts, satellite, site, start: datetime, end: datetime):
    times, codes = satellite.find_events(
        site, _skyfield_time(ts, start), _skyfield_time(ts, end), altitude_degrees=MASK_DEG
    )
    events = []
    for time, code in zip(times, codes, strict=True):
        when = time.utc_datetime()
        event = {"code": int(code), "raw_time": when}
        if code == 1:
            event["culmination_elevation_deg"] = _skyfield_elevation(ts, satellite, site, when)
        else:
            event["refined"] = _refine_skyfield_event(ts, satellite, site, when, int(code))
        events.append(event)
    return events


def _complete_skyfield_passes(events: list[dict]) -> tuple[list[dict], list[dict]]:
    complete, incomplete = [], []
    active = None
    for event in events:
        if event["code"] == 0:
            if active is not None:
                raise ValueError("Skyfield returned consecutive rises without a set")
            active = {"rise": event, "culminations": []}
        elif event["code"] == 1:
            if active is not None:
                active["culminations"].append(event)
        elif active is None:
            incomplete.append({"kind": "set_without_in_interval_rise", "event": event})
        else:
            active["set"] = event
            complete.append(active)
            active = None
    if active is not None:
        incomplete.append({"kind": "rise_without_in_interval_set", "event": active["rise"]})
    return complete, incomplete


def _pointwise_samples(case, events):
    start, end = (datetime.fromisoformat(case[key]) for key in ("start", "end"))
    step = timedelta(seconds=case["point_step_s"])
    samples = set()
    current = start
    while current < end:
        samples.add(current)
        current += step
    samples.add(end)
    for event in events:
        if event["code"] in (0, 2):
            crossing = event["refined"]["time"]
            for offset in (-30, 0, 30):
                when = crossing + timedelta(seconds=offset)
                if start <= when <= end:
                    samples.add(when)
    return sorted(samples)


def characterize_case(case: dict, ts, satellite, propagator) -> dict:
    station = GroundStation(**case["station"])
    site = wgs84.latlon(station.latitude_deg, station.longitude_deg, elevation_m=station.height_m)
    start, end = (datetime.fromisoformat(case[key]) for key in ("start", "end"))
    sf_events = _skyfield_events(ts, satellite, site, start, end)
    sf_passes, incomplete_events = _complete_skyfield_passes(sf_events)
    production_windows = find_satellite_access_windows(
        propagator, station, _astropy_time(start), _astropy_time(end)
    )
    normal_windows = [
        window
        for window in production_windows
        if not window.start_clipped and not window.end_clipped
    ]
    if len(normal_windows) != len(sf_passes):
        raise ValueError(
            f"{case['name']} complete-window count mismatch: "
            f"production {len(normal_windows)}, Skyfield {len(sf_passes)}"
        )

    pairs = []
    for window, sf_pass in zip(normal_windows, sf_passes, strict=True):
        rise = sf_pass["rise"]
        setting = sf_pass["set"]
        if not (
            window.start < _astropy_time(setting["refined"]["time"])
            and _astropy_time(rise["refined"]["time"]) < window.end
        ):
            raise ValueError(f"{case['name']} intervals do not correspond chronologically")
        culmination_deg = max(
            event["culmination_elevation_deg"] for event in sf_pass["culminations"]
        )
        events = {}
        for label, production_time, sf_event in (
            ("rise", window.start, rise),
            ("set", window.end, setting),
        ):
            raw = sf_event["raw_time"]
            refined = sf_event["refined"]["time"]
            events[label] = {
                "production_utc": _utc_datetime(production_time).isoformat(),
                "skyfield_raw_utc": raw.isoformat(),
                "skyfield_refined_utc": refined.isoformat(),
                "production_minus_raw_s": _seconds_between(production_time, raw),
                "production_minus_refined_s": _seconds_between(production_time, refined),
                "skyfield_mask_at_production_deg": _skyfield_elevation(
                    ts, satellite, site, _utc_datetime(production_time)
                )
                - MASK_DEG,
                "production_mask_at_skyfield_refined_deg": satellite_elevation_deg(
                    propagator, station, _astropy_time(refined)
                )
                - MASK_DEG,
                "skyfield_bisection_width_s": sf_event["refined"]["final_width_s"],
                "skyfield_bisection_mask_residual_deg": sf_event["refined"]["mask_residual_deg"],
                "skyfield_initial_bracket_half_width_s": sf_event["refined"][
                    "bracket_half_width_s"
                ],
            }
        pairs.append(
            {
                "culmination_deg": culmination_deg,
                "ordinary_for_timing": culmination_deg >= ORDINARY_CULMINATION_MIN_DEG,
                "rise": events["rise"],
                "set": events["set"],
            }
        )

    sampled = []
    for when in _pointwise_samples(case, sf_events):
        production = satellite_elevation_deg(propagator, station, _astropy_time(when))
        skyfield = _skyfield_elevation(ts, satellite, site, when)
        sampled.append((when, production - skyfield))
    largest_time, largest_residual = max(sampled, key=lambda item: abs(item[1]))
    rms = sqrt(sum(residual**2 for _, residual in sampled) / len(sampled))
    near_crossings = []
    for event in sf_events:
        if event["code"] in (0, 2):
            crossing = event["refined"]["time"]
            nearby = {
                str(offset): next(
                    (
                        residual
                        for time, residual in sampled
                        if time == crossing + timedelta(seconds=offset)
                    ),
                    None,
                )
                for offset in (-30, 0, 30)
            }
            near_crossings.append(
                {"code": event["code"], "refined_utc": crossing.isoformat(), "delta_el_deg": nearby}
            )

    return {
        "name": case["name"],
        "station": case["station"],
        "start_utc": start.isoformat(),
        "end_utc": end.isoformat(),
        "mask_deg": MASK_DEG,
        "pointwise_sample_count": len(sampled),
        "pointwise_max_abs_delta_el_deg": abs(largest_residual),
        "pointwise_signed_delta_el_at_max_deg": largest_residual,
        "pointwise_max_time_utc": largest_time.isoformat(),
        "pointwise_rms_delta_el_deg": rms,
        "near_crossings": near_crossings,
        "production_total_windows": len(production_windows),
        "production_complete_windows": len(normal_windows),
        "production_clipped_windows": [
            {
                "start_utc": _utc_datetime(window.start).isoformat(),
                "end_utc": _utc_datetime(window.end).isoformat(),
                "start_clipped": window.start_clipped,
                "end_clipped": window.end_clipped,
            }
            for window in production_windows
            if window.start_clipped or window.end_clipped
        ],
        "skyfield_complete_windows": len(sf_passes),
        "skyfield_raw_rises": sum(event["code"] == 0 for event in sf_events),
        "skyfield_raw_sets": sum(event["code"] == 2 for event in sf_events),
        "skyfield_culminations": [
            {
                "time_utc": event["raw_time"].isoformat(),
                "elevation_deg": event["culmination_elevation_deg"],
            }
            for event in sf_events
            if event["code"] == 1
        ],
        "skyfield_incomplete_events": [
            {
                "kind": item["kind"],
                "code": item["event"]["code"],
                "time_utc": item["event"]["raw_time"].isoformat(),
            }
            for item in incomplete_events
        ],
        "paired_complete_windows": pairs,
    }


def characterize_phase_a() -> dict:
    ts = load.timescale(builtin=True)
    line1, line2 = TLE_FIXTURE["tle_line1"], TLE_FIXTURE["tle_line2"]
    tle = TleRecord.from_lines(line1, line2, source=TLE_FIXTURE["tle_provenance"])
    propagator = Sgp4Propagator(tle)
    satellite = EarthSatellite(line1, line2, ts=ts)
    if satellite.model.satnum != tle.catalog_id or satellite.model.satnum != 5:
        raise ValueError("Skyfield and production TLE catalogue identifiers differ")
    if abs((_astropy_time(satellite.epoch.utc_datetime()) - tle.epoch).to_value(u.s)) > 0.001:
        raise ValueError("Skyfield and production TLE epochs differ by more than 1 ms")
    if (satellite.model.mu, satellite.model.radiusearthkm) != (
        propagator._satellite.mu,
        propagator._satellite.radiusearthkm,
    ):
        raise ValueError("Skyfield and production SGP4 gravity constants differ")

    with _matched_eop(ts) as dut1_by_day:
        checks = [
            datetime(2000, 6, 27, 0, tzinfo=UTC),
            datetime(2000, 6, 27, 12, 34, 56, 789000, tzinfo=UTC),
            datetime(2000, 6, 27, 20, 11, 0, 900000, tzinfo=UTC),
            datetime(2000, 6, 28, 0, tzinfo=UTC),
        ]
        dut1_residuals = [
            float(_astropy_time(when).delta_ut1_utc - _skyfield_time(ts, when).dut1)
            for when in checks
        ]
        cases = [characterize_case(case, ts, satellite, propagator) for case in CASES]
    ordinary_events = [
        pair[event]["production_minus_refined_s"]
        for case in cases
        for pair in case["paired_complete_windows"]
        if pair["ordinary_for_timing"]
        for event in ("rise", "set")
    ]
    if not ordinary_events or not all(isfinite(value) for value in ordinary_events):
        raise ValueError("no finite ordinary timing events available for characterization")
    return {
        "versions": {
            name: __import__(name).__version__ for name in ("skyfield", "sgp4", "astropy", "scipy")
        },
        "tle_catalog_id": tle.catalog_id,
        "tle_epoch_utc": tle.epoch.isot,
        "skyfield_epoch_utc": satellite.epoch.utc_datetime().isoformat(),
        "sgp4_mu_km3_s2": satellite.model.mu,
        "sgp4_radius_km": satellite.model.radiusearthkm,
        "dut1_by_day_s": dut1_by_day,
        "max_abs_dut1_interpolation_residual_s": max(abs(value) for value in dut1_residuals),
        "polar_motion_arcsec": {"xp": 0.0, "yp": 0.0},
        "cases": cases,
        "aggregate": {
            "ordinary_event_count": len(ordinary_events),
            "max_abs_refined_timing_residual_s": max(abs(value) for value in ordinary_events),
            "rms_refined_timing_residual_s": sqrt(
                sum(value * value for value in ordinary_events) / len(ordinary_events)
            ),
            "max_abs_pointwise_delta_el_deg": max(
                case["pointwise_max_abs_delta_el_deg"] for case in cases
            ),
            "complete_window_count_agreement": all(
                case["production_complete_windows"] == case["skyfield_complete_windows"]
                for case in cases
            ),
        },
    }


if __name__ == "__main__":
    print(json.dumps(characterize_phase_a(), indent=2))
