"""Versioned archived analysis input, validated before scientific execution."""

import json
import re
from collections.abc import Mapping
from math import isfinite
from pathlib import Path

from astropy.time import Time

from .orbit import TleRecord
from .run import AnalysisConfig
from .stations import GroundStation

INPUT_SCHEMA_VERSION = "1.0"
_UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z\Z")
_REQUIRED = frozenset(
    {
        "schema_version",
        "tle_line1",
        "tle_line2",
        "tle_source",
        "analysis_start_utc",
        "analysis_end_utc",
        "stations",
        "earth_orientation_source",
    }
)
_OPTIONAL = frozenset(
    {"minimum_elevation_deg", "coarse_step_s", "root_tolerance_s", "source_revision"}
)
_STATION_FIELDS = frozenset({"name", "latitude_deg", "longitude_deg", "height_m"})


class InputConfigError(ValueError):
    """The input contract is invalid; no scientific run was attempted."""


def _fields(
    value: object, label: str, required: frozenset[str], optional: frozenset[str] = frozenset()
) -> Mapping:
    if not isinstance(value, Mapping):
        raise InputConfigError(f"{label} must be an object")
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing:
        raise InputConfigError(f"{label} missing required field: {sorted(missing)[0]}")
    if unknown:
        raise InputConfigError(f"{label} has unknown field: {sorted(map(str, unknown))[0]}")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputConfigError(f"{label} must be a nonempty string")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise InputConfigError(f"{label} must be a finite number")
    return float(value)


def _time(value: object, label: str) -> Time:
    if not isinstance(value, str) or not _UTC_TIMESTAMP.fullmatch(value):
        raise InputConfigError(f"{label} must be a scalar UTC ISO-8601 timestamp ending in Z")
    try:
        return Time(value[:-1], format="isot", scale="utc")
    except ValueError as exc:
        raise InputConfigError(f"{label} is not a valid UTC timestamp") from exc


def parse_analysis_config(value: Mapping) -> AnalysisConfig:
    """Build the existing run configuration from strict input-schema 1.0 data."""
    data = _fields(value, "input", _REQUIRED, _OPTIONAL)
    if data["schema_version"] != INPUT_SCHEMA_VERSION or not isinstance(
        data["schema_version"], str
    ):
        raise InputConfigError(f"unsupported input schema_version: {data['schema_version']!r}")
    try:
        tle = TleRecord.from_lines(
            data["tle_line1"], data["tle_line2"], source=_text(data["tle_source"], "tle_source")
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, InputConfigError):
            raise
        raise InputConfigError(f"tle: {exc}") from exc

    stations_data = data["stations"]
    if not isinstance(stations_data, list) or not stations_data:
        raise InputConfigError("stations must be a nonempty array")
    stations = []
    for index, item in enumerate(stations_data):
        label = f"stations[{index}]"
        station = _fields(item, label, _STATION_FIELDS)
        try:
            stations.append(
                GroundStation(
                    _text(station["name"], f"{label}.name"),
                    _number(station["latitude_deg"], f"{label}.latitude_deg"),
                    _number(station["longitude_deg"], f"{label}.longitude_deg"),
                    _number(station["height_m"], f"{label}.height_m"),
                )
            )
        except ValueError as exc:
            raise InputConfigError(f"{label}: {exc}") from exc

    options = {}
    for key in ("minimum_elevation_deg", "coarse_step_s", "root_tolerance_s"):
        if key in data:
            options[key] = _number(data[key], key)
    if "source_revision" in data:
        revision = data["source_revision"]
        options["source_revision"] = (
            None if revision is None else _text(revision, "source_revision")
        )
    try:
        return AnalysisConfig(
            tle,
            _time(data["analysis_start_utc"], "analysis_start_utc"),
            _time(data["analysis_end_utc"], "analysis_end_utc"),
            tuple(stations),
            earth_orientation_source=_text(
                data["earth_orientation_source"], "earth_orientation_source"
            ),
            **options,
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, InputConfigError):
            raise
        raise InputConfigError(f"analysis: {exc}") from exc


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputConfigError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise InputConfigError(f"nonfinite JSON number: {value}")


def load_analysis_config(path: str | Path) -> AnalysisConfig:
    """Read UTF-8 JSON and reject malformed input before calling run_analysis."""
    try:
        data = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputConfigError(f"input JSON could not be read: {exc}") from exc
    return parse_analysis_config(data)
