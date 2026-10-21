"""Versioned archived analysis input, validated before scientific execution."""

import json
import os
import re
from collections.abc import Mapping
from hashlib import sha256
from math import isfinite
from pathlib import Path, PurePosixPath, PureWindowsPath

from astropy.time import Time

from .eop import EarthOrientationConfig
from .orbit import TleRecord
from .run import AnalysisConfig
from .stations import GroundStation

INPUT_SCHEMA_VERSION = "1.1"
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
        "earth_orientation_mode",
        "earth_orientation_source",
    }
)
_OPTIONAL = frozenset(
    {
        "minimum_elevation_deg",
        "coarse_step_s",
        "root_tolerance_s",
        "source_revision",
        "earth_orientation_table_file",
    }
)
_STATION_FIELDS = frozenset({"name", "latitude_deg", "longitude_deg", "height_m"})
_EOP_FIELDS = frozenset({"mjd", "ut1_minus_utc_s", "xp_arcsec", "yp_arcsec"})


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


def _explicit_eop(data: Mapping, base_dir: Path) -> EarthOrientationConfig:
    reference = _text(data["earth_orientation_table_file"], "earth_orientation_table_file")
    windows_path = PureWindowsPath(reference)
    if PurePosixPath(reference).is_absolute() or windows_path.drive or windows_path.root:
        raise InputConfigError("earth_orientation_table_file must be relative to the config file")
    try:
        target = (base_dir / reference).resolve()
        identity = Path(os.path.relpath(target, base_dir.resolve())).as_posix()
        content = target.read_bytes()
    except (OSError, ValueError) as exc:
        raise InputConfigError(
            f"earth_orientation_table_file {reference!r} could not be resolved or read: {exc}"
        ) from exc
    try:
        table = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise InputConfigError(
            f"earth_orientation_table_file {reference!r} is not valid UTF-8 JSON: {exc}"
        ) from exc
    values = _fields(table, "Earth-orientation table", _EOP_FIELDS)
    columns = []
    for key in ("mjd", "ut1_minus_utc_s", "xp_arcsec", "yp_arcsec"):
        column = values[key]
        if not isinstance(column, list) or len(column) < 2:
            raise InputConfigError(
                f"Earth-orientation {key} must be an array with at least two values"
            )
        columns.append(column)
    if len({len(column) for column in columns}) != 1:
        raise InputConfigError("Earth-orientation columns must have equal lengths")
    days = columns[0]
    if any(type(day) is not int for day in days) or any(a >= b for a, b in zip(days, days[1:])):
        raise InputConfigError("Earth-orientation mjd must be strictly increasing integer days")
    rows = tuple(
        (
            day,
            *(
                _number(columns[index][row], f"Earth-orientation {key}[{row}]")
                for index, key in enumerate(("ut1_minus_utc_s", "xp_arcsec", "yp_arcsec"), start=1)
            ),
        )
        for row, day in enumerate(days)
    )
    return EarthOrientationConfig(
        "explicit_table",
        _text(data["earth_orientation_source"], "earth_orientation_source"),
        identity,
        sha256(content).hexdigest(),
        rows,
    )


def parse_analysis_config(value: Mapping, *, base_dir: str | Path | None = None) -> AnalysisConfig:
    """Build input-schema 1.1 data; relative table files need a config directory."""
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
    mode = _text(data["earth_orientation_mode"], "earth_orientation_mode")
    source = _text(data["earth_orientation_source"], "earth_orientation_source")
    if mode == "configured_iers":
        if "earth_orientation_table_file" in data:
            raise InputConfigError("configured_iers cannot specify earth_orientation_table_file")
        earth_orientation = EarthOrientationConfig(mode, source)
    elif mode == "explicit_table":
        if "earth_orientation_table_file" not in data:
            raise InputConfigError("explicit_table requires earth_orientation_table_file")
        if base_dir is None:
            raise InputConfigError("explicit_table requires the config file directory")
        earth_orientation = _explicit_eop(data, Path(base_dir))
    else:
        raise InputConfigError(f"unsupported earth_orientation_mode: {mode!r}")
    try:
        return AnalysisConfig(
            tle,
            _time(data["analysis_start_utc"], "analysis_start_utc"),
            _time(data["analysis_end_utc"], "analysis_end_utc"),
            tuple(stations),
            earth_orientation=earth_orientation,
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
    return parse_analysis_config(data, base_dir=Path(path).resolve().parent)
