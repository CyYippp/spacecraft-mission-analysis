"""Threshold access windows from a scalar UTC elevation evaluator."""

from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from numbers import Real

import astropy.units as u
from astropy.time import Time
from scipy.optimize import brentq, minimize_scalar

PEAK_XATOL_S = 0.002  # Numerical refinement width, not pass-time accuracy.


@dataclass(frozen=True, slots=True)
class AccessWindow:
    """Positive-elevation interval; endpoints may be threshold events or clipped bounds."""

    _start_jd1: float
    _start_jd2: float
    _end_jd1: float
    _end_jd2: float
    _max_jd1: float
    _max_jd2: float
    max_elevation_deg: float
    start_clipped: bool = False
    end_clipped: bool = False

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError("access end must not precede start")
        if not self.start <= self.max_elevation_time <= self.end:
            raise ValueError("maximum elevation time must lie within the access window")
        _finite_number(self.max_elevation_deg, "max_elevation_deg")

    @property
    def start(self) -> Time:
        return Time(self._start_jd1, self._start_jd2, format="jd", scale="utc")

    @property
    def end(self) -> Time:
        return Time(self._end_jd1, self._end_jd2, format="jd", scale="utc")

    @property
    def max_elevation_time(self) -> Time:
        return Time(self._max_jd1, self._max_jd2, format="jd", scale="utc")

    @property
    def duration_s(self) -> float:
        return float((self.end - self.start).to_value(u.s))


def _utc_scalar(value: Time, name: str) -> None:
    if not isinstance(value, Time) or not value.isscalar or value.scale != "utc":
        raise TypeError(f"{name} must be a scalar astropy.time.Time in UTC")


def _finite_number(value: float, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    result = float(value)
    if positive and result <= 0:
        raise ValueError(f"{name} must be positive")
    return result


def find_access_windows(
    elevation_deg_at: Callable[[Time], float],
    start: Time,
    end: Time,
    *,
    minimum_elevation_deg: float,
    coarse_step_s: float = 5.0,
    root_tolerance_s: float = 0.01,
) -> tuple[AccessWindow, ...]:
    """Find sampled positive intervals and refine sign-changing endpoints.

    Access means elevation > threshold. A sampled zero is an exact boundary;
    an unsampled positive interval can be missed by the finite coarse grid.
    """
    if not callable(elevation_deg_at):
        raise TypeError("elevation_deg_at must be callable")
    _utc_scalar(start, "start")
    _utc_scalar(end, "end")
    duration_s = float((end - start).to_value(u.s))
    if not isfinite(duration_s) or duration_s <= 0:
        raise ValueError("analysis end must be after start")
    threshold = _finite_number(minimum_elevation_deg, "minimum_elevation_deg")
    step = _finite_number(coarse_step_s, "coarse_step_s", positive=True)
    tolerance = _finite_number(root_tolerance_s, "root_tolerance_s", positive=True)

    def elevation(time: Time) -> float:
        return _finite_number(elevation_deg_at(time), "evaluated elevation")

    def residual(time: Time) -> float:
        return elevation(time) - threshold

    offsets = [i * step for i in range(int(duration_s / step) + 1) if i * step < duration_s]
    offsets.append(duration_s)
    times = [
        start if offset == 0 else end if offset == duration_s else start + offset * u.s
        for offset in offsets
    ]
    values = [residual(time) for time in times]

    def crossing(left: int, right: int) -> Time:
        if values[left] == 0:
            return times[left]
        if values[right] == 0:
            return times[right]
        left_time = times[left]
        width_s = float((times[right] - left_time).to_value(u.s))
        offset_s = brentq(
            lambda elapsed_s: residual(left_time + elapsed_s * u.s),
            0.0,
            width_s,
            xtol=tolerance,
        )
        return left_time + offset_s * u.s

    def window(first: Time, last: Time, first_clipped: bool, last_clipped: bool) -> AccessWindow:
        # Retain detection-grid samples so grid-visible secondary peaks are not
        # discarded by a single bounded search over a possibly multimodal window.
        candidates = [(first, elevation(first))]
        candidates.extend(
            (time, value + threshold) for time, value in zip(times, values) if first < time < last
        )
        candidates.append((last, elevation(last)))

        def refine(left: Time, right: Time) -> None:
            width_s = float((right - left).to_value(u.s))
            result = minimize_scalar(
                lambda elapsed_s: -elevation(left + elapsed_s * u.s),
                bounds=(0.0, width_s),
                method="bounded",
                options={"xatol": PEAK_XATOL_S},
            )
            if not result.success or not isfinite(result.x) or not 0 <= result.x <= width_s:
                raise RuntimeError("maximum elevation optimization failed")
            peak_time = left + result.x * u.s
            candidates.append((peak_time, elevation(peak_time)))

        refine(first, last)
        sampled = candidates[:-1]  # Exclude the full-window optimizer candidate.
        for index in range(1, len(sampled) - 1):
            if (
                sampled[index][1] >= sampled[index - 1][1]
                and sampled[index][1] >= sampled[index + 1][1]
            ):
                if sampled[index][1] > min(sampled[index - 1][1], sampled[index + 1][1]):
                    refine(sampled[index - 1][0], sampled[index + 1][0])

        peak_time, peak_elevation = max(
            candidates,
            key=lambda item: (item[1], -float((item[0] - first).to_value(u.s))),
        )
        return AccessWindow(
            first.jd1,
            first.jd2,
            last.jd1,
            last.jd2,
            peak_time.jd1,
            peak_time.jd2,
            peak_elevation,
            first_clipped,
            last_clipped,
        )

    windows = []
    entry: Time | None = None
    entry_clipped = False
    for i, value in enumerate(values):
        if value > 0 and entry is None:
            entry = start if i == 0 else crossing(i - 1, i)
            entry_clipped = i == 0
        elif value <= 0 and entry is not None:
            exit_time = crossing(i - 1, i)
            if exit_time > entry:
                windows.append(window(entry, exit_time, entry_clipped, False))
            entry = None
    if entry is not None:
        windows.append(window(entry, end, entry_clipped, True))
    return tuple(windows)
