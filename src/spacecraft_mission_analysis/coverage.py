"""Continuous-time coverage metrics from already detected access intervals."""

from collections.abc import Iterable
from dataclasses import dataclass
from math import fsum, isfinite, nextafter

import astropy.units as u
from astropy.time import Time

from .access import AccessWindow


def _utc_scalar(value: Time, name: str) -> None:
    if not isinstance(value, Time) or not value.isscalar or value.scale != "utc":
        raise TypeError(f"{name} must be a scalar astropy.time.Time in UTC")
    if not isfinite(value.jd1) or not isfinite(value.jd2):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True, slots=True)
class CoverageInterval:
    """UTC interval with split Julian dates retained at the metrics boundary."""

    _start_jd1: float
    _start_jd2: float
    _end_jd1: float
    _end_jd2: float

    def __post_init__(self) -> None:
        _utc_scalar(self.start, "interval start")
        _utc_scalar(self.end, "interval end")
        if self.end < self.start:
            raise ValueError("interval end must not precede start")

    @classmethod
    def from_times(cls, start: Time, end: Time) -> "CoverageInterval":
        _utc_scalar(start, "interval start")
        _utc_scalar(end, "interval end")
        return cls(start.jd1, start.jd2, end.jd1, end.jd2)

    @property
    def start(self) -> Time:
        return Time(self._start_jd1, self._start_jd2, format="jd", scale="utc")

    @property
    def end(self) -> Time:
        return Time(self._end_jd1, self._end_jd2, format="jd", scale="utc")

    @property
    def duration_s(self) -> float:
        return float((self.end - self.start).to_value(u.s))


@dataclass(frozen=True, slots=True)
class TemporalCoverage:
    """Union metrics for access from at least one station over an analysis span."""

    _start_jd1: float
    _start_jd2: float
    _end_jd1: float
    _end_jd2: float
    union_intervals: tuple[CoverageInterval, ...]
    total_access_duration_s: float
    coverage_fraction: float
    access_window_count: int
    longest_no_access_gap_s: float
    longest_no_access_gap: CoverageInterval | None

    @property
    def analysis_start(self) -> Time:
        return Time(self._start_jd1, self._start_jd2, format="jd", scale="utc")

    @property
    def analysis_end(self) -> Time:
        return Time(self._end_jd1, self._end_jd2, format="jd", scale="utc")


def compute_temporal_coverage(
    analysis_start: Time,
    analysis_end: Time,
    intervals: Iterable[CoverageInterval | AccessWindow],
) -> TemporalCoverage:
    """Clip and unite access intervals, then measure coverage and its longest gap.

    The reported span is [start, end]. Isolated endpoints have zero duration;
    intervals touching at an endpoint form one continuous union interval.
    The count is the number of merged union intervals, not station passes.
    Equal longest gaps select the earliest gap.
    """
    _utc_scalar(analysis_start, "analysis start")
    _utc_scalar(analysis_end, "analysis end")
    duration_s = float((analysis_end - analysis_start).to_value(u.s))
    if not isfinite(duration_s) or duration_s <= 0:
        raise ValueError("analysis end must be after start")

    clipped = []
    for interval in intervals:
        if not isinstance(interval, (CoverageInterval, AccessWindow)):
            raise TypeError("intervals must contain CoverageInterval or AccessWindow values")
        start, end = interval.start, interval.end
        _utc_scalar(start, "interval start")
        _utc_scalar(end, "interval end")
        if end < start:
            raise ValueError("interval end must not precede start")
        start = max(start, analysis_start)
        end = min(end, analysis_end)
        if end > start:
            clipped.append((start, end))

    clipped.sort(key=lambda pair: pair[0])
    merged: list[tuple[Time, Time]] = []
    for start, end in clipped:
        if merged and start <= merged[-1][1]:
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))

    union = tuple(CoverageInterval.from_times(start, end) for start, end in merged)
    total_s = fsum(interval.duration_s for interval in union)
    fraction = total_s / duration_s
    if fraction > 1 and fraction <= nextafter(1.0, float("inf")):
        fraction = 1.0  # Only a one-ULP arithmetic excess is permitted.
    if not 0 <= fraction <= 1:
        raise ArithmeticError("coverage fraction lies outside [0, 1]")

    cursor = analysis_start
    longest_gap: CoverageInterval | None = None
    longest_gap_s = 0.0
    for next_start, next_end in [*merged, (analysis_end, analysis_end)]:
        gap_s = float((next_start - cursor).to_value(u.s))
        if gap_s > longest_gap_s:
            longest_gap_s = gap_s
            longest_gap = CoverageInterval.from_times(cursor, next_start)
        cursor = next_end

    return TemporalCoverage(
        analysis_start.jd1,
        analysis_start.jd2,
        analysis_end.jd1,
        analysis_end.jd2,
        union,
        total_s,
        fraction,
        len(union),
        longest_gap_s,
        longest_gap,
    )
