"""Versioned, deterministic JSON and CSV representations of a run result."""

import csv
import io
import json
from dataclasses import asdict
from pathlib import Path

from astropy.time import Time

from .access import PEAK_XATOL_S
from .run import (
    TLE_AGE_WARNING_DAYS,
    VALIDATED_ANALYSIS_SPAN_MAX_HOURS,
    AnalysisResult,
)


def _utc(time: Time) -> str:
    copy = time.utc.replicate()
    copy.precision = 9
    return f"{copy.isot}Z"


def _station(station) -> dict:
    return {
        "name": station.name,
        "latitude_deg": station.latitude_deg,
        "longitude_deg_east": station.longitude_deg,
        "ellipsoidal_height_m": station.height_m,
    }


def _configuration(result: AnalysisResult) -> dict:
    config = result.config
    return {
        "analysis_start_utc": _utc(config.start),
        "analysis_end_utc": _utc(config.end),
        "tle": {
            "line1": config.tle.line1,
            "line2": config.tle.line2,
            "catalog_id": config.tle.catalog_id,
            "epoch_utc": _utc(config.tle.epoch),
            "source": config.tle.source,
        },
        "stations": [_station(station) for station in config.stations],
        "minimum_elevation_deg": config.minimum_elevation_deg,
        "coarse_step_s": config.coarse_step_s,
        "root_tolerance_s": config.root_tolerance_s,
        "peak_refinement_xatol_s": PEAK_XATOL_S,
        "tle_age_warning_days": TLE_AGE_WARNING_DAYS,
        "validated_analysis_span_max_hours": VALIDATED_ANALYSIS_SPAN_MAX_HOURS,
        "earth_orientation_mode": config.earth_orientation.mode,
        "earth_orientation_source": config.earth_orientation_source,
        "earth_orientation_table_identity": config.earth_orientation.table_identity,
        "earth_orientation_table_sha256": config.earth_orientation.table_sha256,
        "source_revision": config.source_revision,
    }


def result_dict(result: AnalysisResult) -> dict:
    """Return the documented JSON shape without exposing Astropy/Python objects."""
    if not isinstance(result, AnalysisResult):
        raise TypeError("result must be an AnalysisResult")
    station_access = None
    if result.station_access is not None:
        station_access = [
            {
                "station_name": item.station.name,
                "windows": [
                    {
                        "start_utc": _utc(window.start),
                        "end_utc": _utc(window.end),
                        "duration_s": window.duration_s,
                        "max_elevation_deg": window.max_elevation_deg,
                        "max_elevation_time_utc": _utc(window.max_elevation_time),
                        "start_clipped": window.start_clipped,
                        "end_clipped": window.end_clipped,
                    }
                    for window in item.windows
                ],
            }
            for item in result.station_access
        ]
    coverage = None
    if result.coverage is not None:
        metric = result.coverage
        coverage = {
            "analysis_start_utc": _utc(metric.analysis_start),
            "analysis_end_utc": _utc(metric.analysis_end),
            "total_access_duration_s": metric.total_access_duration_s,
            "coverage_fraction": metric.coverage_fraction,
            "merged_access_interval_count": metric.access_window_count,
            "longest_no_access_gap_s": metric.longest_no_access_gap_s,
            "longest_gap_start_utc": None
            if metric.longest_no_access_gap is None
            else _utc(metric.longest_no_access_gap.start),
            "longest_gap_end_utc": None
            if metric.longest_no_access_gap is None
            else _utc(metric.longest_no_access_gap.end),
            "union_intervals": [
                {
                    "start_utc": _utc(item.start),
                    "end_utc": _utc(item.end),
                    "duration_s": item.duration_s,
                }
                for item in metric.union_intervals
            ],
        }
    return {
        "schema_version": result.schema_version,
        "status": result.status.value,
        "configuration": _configuration(result),
        "provenance": asdict(result.provenance),
        "notices": [
            {
                "code": notice.code,
                "severity": notice.severity,
                "stage": notice.stage,
                "message": notice.message,
                "details": dict(notice.details),
            }
            for notice in result.notices
        ],
        "station_access": station_access,
        "coverage": coverage,
    }


def serialize_json(result: AnalysisResult) -> str:
    return json.dumps(result_dict(result), sort_keys=True, indent=2, allow_nan=False) + "\n"


def write_json(result: AnalysisResult, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(serialize_json(result), encoding="utf-8", newline="\n")
    return target


def _csv_text(columns: tuple[str, ...], rows: list[dict]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def csv_bundle(result: AnalysisResult) -> dict[str, str]:
    """Return a fixed-membership bundle; failed-result files have headers only."""
    data = result_dict(result)
    config, provenance = data["configuration"], data["provenance"]
    tle = config["tle"]
    run_row = {
        "schema_version": data["schema_version"],
        "status": data["status"],
        "analysis_start_utc": config["analysis_start_utc"],
        "analysis_end_utc": config["analysis_end_utc"],
        "tle_line1": tle["line1"],
        "tle_line2": tle["line2"],
        "tle_catalog_id": tle["catalog_id"],
        "tle_epoch_utc": tle["epoch_utc"],
        "tle_source": tle["source"],
        "minimum_elevation_deg": config["minimum_elevation_deg"],
        "coarse_step_s": config["coarse_step_s"],
        "root_tolerance_s": config["root_tolerance_s"],
        "peak_refinement_xatol_s": config["peak_refinement_xatol_s"],
        "tle_age_warning_days": config["tle_age_warning_days"],
        "validated_analysis_span_max_hours": config["validated_analysis_span_max_hours"],
        "earth_orientation_input_mode": config["earth_orientation_mode"],
        "earth_orientation_source": config["earth_orientation_source"],
        "earth_orientation_table_identity": config["earth_orientation_table_identity"],
        "earth_orientation_table_sha256": config["earth_orientation_table_sha256"],
        "source_revision": config["source_revision"],
        **provenance,
        "notice_count": len(data["notices"]),
    }
    stations = data["configuration"]["stations"]
    windows = []
    if data["station_access"] is not None:
        for station_result in data["station_access"]:
            for window in station_result["windows"]:
                windows.append({"station_name": station_result["station_name"], **window})
    coverage = []
    union = []
    if data["coverage"] is not None:
        coverage = [
            {key: value for key, value in data["coverage"].items() if key != "union_intervals"}
        ]
        union = data["coverage"]["union_intervals"]
    notices = [
        {
            "code": item["code"],
            "severity": item["severity"],
            "stage": item["stage"],
            "message": item["message"],
            "details_json": json.dumps(item["details"], sort_keys=True, separators=(",", ":")),
        }
        for item in data["notices"]
    ]
    tables = {
        "run.csv": (tuple(run_row), [run_row]),
        "stations.csv": (tuple(_station(result.config.stations[0])), stations),
        "access_windows.csv": (
            (
                "station_name",
                "start_utc",
                "end_utc",
                "duration_s",
                "max_elevation_deg",
                "max_elevation_time_utc",
                "start_clipped",
                "end_clipped",
            ),
            windows,
        ),
        "coverage.csv": (
            (
                "analysis_start_utc",
                "analysis_end_utc",
                "total_access_duration_s",
                "coverage_fraction",
                "merged_access_interval_count",
                "longest_no_access_gap_s",
                "longest_gap_start_utc",
                "longest_gap_end_utc",
            ),
            coverage,
        ),
        "union_intervals.csv": (("start_utc", "end_utc", "duration_s"), union),
        "warnings.csv": (("code", "severity", "stage", "message", "details_json"), notices),
    }
    return {name: _csv_text(columns, rows) for name, (columns, rows) in tables.items()}


def write_csv_bundle(result: AnalysisResult, directory: str | Path) -> dict[str, Path]:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    return {
        name: _write_csv_file(target / name, content)
        for name, content in csv_bundle(result).items()
    }


def _write_csv_file(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8", newline="\n")
    return path
