"""Reproducible run boundary around the existing access and coverage kernels."""

from dataclasses import dataclass
from enum import StrEnum
from importlib.metadata import version
from math import isfinite
from numbers import Real

import astropy
import astropy.units as u
import scipy
import sgp4
from astropy.time import Time

from .access import AccessWindow
from .coverage import TemporalCoverage, compute_temporal_coverage
from .elevation import find_satellite_access_windows
from .frames import FrameTransformError
from .orbit import PropagationError, Sgp4Propagator, TleRecord
from .stations import GroundStation

SCHEMA_VERSION = "1.0"
TLE_AGE_WARNING_DAYS = 7.0
VALIDATED_ANALYSIS_SPAN_MAX_HOURS = 24.0


class RunStatus(StrEnum):
    SUCCESS = "SUCCESS"
    SUCCESS_WITH_WARNINGS = "SUCCESS_WITH_WARNINGS"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class RunNotice:
    code: str
    severity: str
    stage: str
    message: str
    details: tuple[tuple[str, float | int | str], ...] = ()


@dataclass(frozen=True, slots=True, init=False)
class AnalysisConfig:
    tle: TleRecord
    _start_jd1: float
    _start_jd2: float
    _end_jd1: float
    _end_jd2: float
    stations: tuple[GroundStation, ...]
    minimum_elevation_deg: float
    coarse_step_s: float
    root_tolerance_s: float
    earth_orientation_source: str
    source_revision: str | None

    def __init__(
        self,
        tle: TleRecord,
        start: Time,
        end: Time,
        stations: tuple[GroundStation, ...],
        *,
        minimum_elevation_deg: float = 10.0,
        coarse_step_s: float = 5.0,
        root_tolerance_s: float = 0.01,
        earth_orientation_source: str = "Astropy configured IERS table",
        source_revision: str | None = None,
    ) -> None:
        if not isinstance(tle, TleRecord):
            raise TypeError("tle must be a TleRecord")
        for label, time in (("start", start), ("end", end)):
            if not isinstance(time, Time) or not time.isscalar or time.scale != "utc":
                raise TypeError(f"{label} must be a scalar astropy.time.Time in UTC")
            if not isfinite(time.jd1) or not isfinite(time.jd2):
                raise ValueError(f"{label} must be finite")
        duration_s = float((end - start).to_value(u.s))
        if not isfinite(duration_s) or duration_s <= 0:
            raise ValueError("analysis end must be after start")
        stations = tuple(stations)
        if not stations or any(not isinstance(item, GroundStation) for item in stations):
            raise ValueError("stations must contain one or more GroundStation values")
        if len({item.name for item in stations}) != len(stations):
            raise ValueError("station names must be unique within a run")
        for label, value, positive in (
            ("minimum_elevation_deg", minimum_elevation_deg, False),
            ("coarse_step_s", coarse_step_s, True),
            ("root_tolerance_s", root_tolerance_s, True),
        ):
            if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
                raise ValueError(f"{label} must be finite")
            if positive and value <= 0:
                raise ValueError(f"{label} must be positive")
        if not isinstance(earth_orientation_source, str) or not earth_orientation_source.strip():
            raise ValueError("earth_orientation_source must be a nonempty source label")
        if source_revision is not None and (
            not isinstance(source_revision, str) or not source_revision.strip()
        ):
            raise ValueError("source_revision must be a nonempty string if supplied")
        for name, value in (
            ("tle", tle),
            ("_start_jd1", start.jd1),
            ("_start_jd2", start.jd2),
            ("_end_jd1", end.jd1),
            ("_end_jd2", end.jd2),
            ("stations", stations),
            ("minimum_elevation_deg", float(minimum_elevation_deg)),
            ("coarse_step_s", float(coarse_step_s)),
            ("root_tolerance_s", float(root_tolerance_s)),
            ("earth_orientation_source", earth_orientation_source),
            ("source_revision", source_revision),
        ):
            object.__setattr__(self, name, value)

    @property
    def start(self) -> Time:
        return Time(self._start_jd1, self._start_jd2, format="jd", scale="utc")

    @property
    def end(self) -> Time:
        return Time(self._end_jd1, self._end_jd2, format="jd", scale="utc")


@dataclass(frozen=True, slots=True)
class StationAccess:
    station: GroundStation
    windows: tuple[AccessWindow, ...]


@dataclass(frozen=True, slots=True)
class RunProvenance:
    project_version: str
    sgp4_version: str
    astropy_version: str
    scipy_version: str
    sgp4_gravity_constants: str = "WGS72"
    station_ellipsoid: str = "WGS84"
    sgp4_output_frame: str = "TEME"
    earth_orientation_mode: str = "Astropy IERS"


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    schema_version: str
    status: RunStatus
    config: AnalysisConfig
    provenance: RunProvenance
    notices: tuple[RunNotice, ...]
    station_access: tuple[StationAccess, ...] | None
    coverage: TemporalCoverage | None

    def __post_init__(self) -> None:
        if self.status == RunStatus.FAILED:
            if self.station_access is not None or self.coverage is not None:
                raise ValueError("failed runs cannot contain access or coverage results")
            if not any(notice.severity == "ERROR" for notice in self.notices):
                raise ValueError("failed runs require an error notice")
        elif self.station_access is None or self.coverage is None:
            raise ValueError("successful runs require completed access and coverage results")


def _provenance() -> RunProvenance:
    return RunProvenance(
        version("spacecraft-mission-analysis"),
        sgp4.__version__,
        astropy.__version__,
        scipy.__version__,
    )


def run_analysis(config: AnalysisConfig) -> AnalysisResult:
    """Execute one archived-TLE analysis; required kernel failures discard all results."""
    if not isinstance(config, AnalysisConfig):
        raise TypeError("config must be an AnalysisConfig")
    provenance = _provenance()
    start, end = config.start, config.end
    max_age_days = max(
        abs((start - config.tle.epoch).to_value(u.day)),
        abs((end - config.tle.epoch).to_value(u.day)),
    )
    duration_hours = float((end - start).to_value(u.hour))
    notices: list[RunNotice] = []
    if max_age_days > TLE_AGE_WARNING_DAYS:
        notices.append(
            RunNotice(
                "TLE_AGE_WARNING",
                "WARNING",
                "input_validity",
                "Analysis extends beyond the 7-day TLE-age workflow warning threshold; orbit accuracy is not certified.",
                (
                    ("max_abs_age_days", float(max_age_days)),
                    ("threshold_days", TLE_AGE_WARNING_DAYS),
                ),
            )
        )
    if duration_hours > VALIDATED_ANALYSIS_SPAN_MAX_HOURS:
        notices.append(
            RunNotice(
                "ANALYSIS_SPAN_OUTSIDE_VALIDATED_ENVELOPE",
                "WARNING",
                "evidence_envelope",
                "Analysis duration exceeds the 24-hour duration envelope exercised by current comparison evidence; computation may still succeed.",
                (
                    ("analysis_span_hours", duration_hours),
                    ("validated_max_hours", VALIDATED_ANALYSIS_SPAN_MAX_HOURS),
                ),
            )
        )

    propagator = Sgp4Propagator(config.tle)
    by_station: list[StationAccess] = []
    try:
        for station in config.stations:
            windows = find_satellite_access_windows(
                propagator,
                station,
                start,
                end,
                minimum_elevation_deg=config.minimum_elevation_deg,
                coarse_step_s=config.coarse_step_s,
                root_tolerance_s=config.root_tolerance_s,
            )
            by_station.append(StationAccess(station, windows))
    except PropagationError as exc:
        notices.append(
            RunNotice(
                "SGP4_PROPAGATION_ERROR",
                "ERROR",
                "propagation",
                str(exc),
                (("sgp4_error_code", exc.code),),
            )
        )
    except FrameTransformError as exc:
        notices.append(RunNotice("EOP_UNAVAILABLE", "ERROR", "frame", str(exc)))

    if notices and notices[-1].severity == "ERROR":
        return AnalysisResult(
            SCHEMA_VERSION, RunStatus.FAILED, config, provenance, tuple(notices), None, None
        )

    windows = (window for item in by_station for window in item.windows)
    coverage = compute_temporal_coverage(start, end, windows)
    status = RunStatus.SUCCESS_WITH_WARNINGS if notices else RunStatus.SUCCESS
    return AnalysisResult(
        SCHEMA_VERSION, status, config, provenance, tuple(notices), tuple(by_station), coverage
    )
