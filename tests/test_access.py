"""Analytic threshold events, boundary cases, and finite-grid behaviour."""

from dataclasses import FrozenInstanceError
from math import sqrt

import astropy.units as u
import pytest
from astropy.time import Time

from spacecraft_mission_analysis import AccessWindow, find_access_windows

START = Time("2000-06-27T00:00:00", scale="utc")
ROOT_TOLERANCE_S = 0.01  # Numerical Brent xtol, fixed before observing results.
PEAK_TIME_LIMIT_S = 0.02  # Analytic recovery criterion, declared before orbit peak evaluation.
PEAK_ELEVATION_LIMIT_DEG = 1e-5  # Separate synthetic angle criterion, not physical accuracy.
ROOT_1_S = 10 - sqrt(20)
ROOT_2_S = 10 + sqrt(20)


def at(second: float) -> Time:
    return START + second * u.s


def seconds(time: Time) -> float:
    return float((time - START).to_value(u.s))


def parabola(time: Time) -> float:
    t = seconds(time)
    return 20 - 0.5 * (t - 10) ** 2


def solve(evaluator=parabola, begin=0, finish=20, step=5):
    return find_access_windows(
        evaluator,
        at(begin),
        at(finish),
        minimum_elevation_deg=10,
        coarse_step_s=step,
        root_tolerance_s=ROOT_TOLERANCE_S,
    )


def test_analytic_entry_and_exit() -> None:
    (window,) = solve()
    assert isinstance(window, AccessWindow)
    assert not window.start_clipped and not window.end_clipped
    assert abs(seconds(window.start) - ROOT_1_S) <= ROOT_TOLERANCE_S
    assert abs(seconds(window.end) - ROOT_2_S) <= ROOT_TOLERANCE_S
    assert window.duration_s == pytest.approx(seconds(window.end) - seconds(window.start), abs=1e-9)
    assert window.duration_s > 0
    assert abs(seconds(window.max_elevation_time) - 10.0) <= PEAK_TIME_LIMIT_S
    assert abs(window.max_elevation_deg - 20.0) <= PEAK_ELEVATION_LIMIT_DEG
    returned_peak_time = window.max_elevation_time
    returned_peak_time.format = "mjd"
    assert window.max_elevation_time.format == "jd"
    with pytest.raises(FrozenInstanceError):
        window.start_clipped = True
    with pytest.raises(FrozenInstanceError):
        window.max_elevation_deg = 0.0


def test_no_pass_and_entire_interval() -> None:
    assert solve(lambda _: 9.0) == ()
    (whole,) = solve(lambda _: 11.0)
    assert whole.start == at(0) and whole.end == at(20)
    assert whole.start_clipped and whole.end_clipped
    assert whole.duration_s == pytest.approx(20.0, abs=1e-9)
    assert whole.max_elevation_time == whole.start
    assert whole.max_elevation_deg == 11.0


def test_asymmetric_smooth_interior_peak() -> None:
    # On [0, 20], the positive factor leaves the unique global peak at t=8.
    def asymmetric(time: Time) -> float:
        offset = seconds(time) - 8.0
        return 20.0 - 0.3 * offset**2 * (1.0 + 0.04 * offset)

    (window,) = solve(asymmetric)
    assert not window.start_clipped and not window.end_clipped
    assert abs(seconds(window.max_elevation_time) - 8.0) <= PEAK_TIME_LIMIT_S
    assert abs(window.max_elevation_deg - 20.0) <= PEAK_ELEVATION_LIMIT_DEG


def test_start_boundary_peak() -> None:
    (window,) = solve(lambda time: 15.0 - 0.1 * seconds(time))
    assert window.start_clipped and window.end_clipped
    assert window.max_elevation_time == window.start
    assert window.max_elevation_deg == 15.0


def test_end_boundary_peak() -> None:
    (window,) = solve(lambda time: 11.0 + 0.1 * seconds(time))
    assert window.start_clipped and window.end_clipped
    assert window.max_elevation_time == window.end
    assert window.max_elevation_deg == pytest.approx(13.0, abs=PEAK_ELEVATION_LIMIT_DEG)


def test_very_short_window_peak() -> None:
    (window,) = solve(
        lambda time: 20.0 - 0.5 * (seconds(time) - 0.0005) ** 2,
        begin=0,
        finish=0.001,
    )
    assert window.duration_s == pytest.approx(0.001, abs=1e-9)
    assert window.start <= window.max_elevation_time <= window.end
    assert abs(seconds(window.max_elevation_time) - 0.0005) <= 0.0005
    assert abs(window.max_elevation_deg - 20.0) <= PEAK_ELEVATION_LIMIT_DEG


def test_flat_and_nearly_flat_peak_time_semantics() -> None:
    (flat,) = solve(lambda _: 20.0)
    assert flat.max_elevation_deg == 20.0
    assert flat.max_elevation_time == flat.start  # Earliest candidate wins an exact tie.

    (nearly_flat,) = solve(lambda time: 20.0 - 1e-12 * (seconds(time) - 10.0) ** 2)
    assert nearly_flat.start <= nearly_flat.max_elevation_time <= nearly_flat.end
    assert abs(nearly_flat.max_elevation_deg - 20.0) <= 1e-9
    # A near-flat peak has no defensible subsecond timestamp criterion.


def test_grid_visible_secondary_peak_cannot_replace_higher_peak() -> None:
    def two_peaks(time: Time) -> float:
        second = seconds(time)
        return 30.0 - min(0.2 * (second - 5.0) ** 2, 1.0 + 0.2 * (second - 15.0) ** 2)

    (window,) = solve(two_peaks)
    assert window.start_clipped and window.end_clipped
    assert abs(seconds(window.max_elevation_time) - 5.0) <= PEAK_TIME_LIMIT_S
    assert abs(window.max_elevation_deg - 30.0) <= PEAK_ELEVATION_LIMIT_DEG


def test_clipped_start_and_end() -> None:
    (start_clipped,) = solve(begin=10)
    assert start_clipped.start == at(10)
    assert start_clipped.start_clipped and not start_clipped.end_clipped
    assert abs(seconds(start_clipped.end) - ROOT_2_S) <= ROOT_TOLERANCE_S

    (end_clipped,) = solve(finish=10)
    assert end_clipped.end == at(10)
    assert not end_clipped.start_clipped and end_clipped.end_clipped
    assert abs(seconds(end_clipped.start) - ROOT_1_S) <= ROOT_TOLERANCE_S


def test_exact_grid_crossings_are_single_events() -> None:
    # The positive portion of this tent function is exactly (5, 15).
    (window,) = solve(lambda time: 10 + min(seconds(time) - 5, 15 - seconds(time)))
    assert window.start == at(5)
    assert window.end == at(15)
    assert not window.start_clipped and not window.end_clipped


def test_tangent_below_on_both_sides_creates_no_access() -> None:
    assert solve(lambda time: 10 - (seconds(time) - 10) ** 2) == ()


def test_narrow_positive_pass_exposes_finite_grid_detection_limit() -> None:
    # Positive on (1.8, 3.0) s; the 5 s grid has no positive sample.
    def narrow(time: Time) -> float:
        return 10 + 0.36 - (seconds(time) - 2.4) ** 2

    assert solve(narrow, finish=5, step=5) == ()
    (detected,) = solve(narrow, finish=5, step=1)
    assert abs(seconds(detected.start) - 1.8) <= ROOT_TOLERANCE_S
    assert abs(seconds(detected.end) - 3.0) <= ROOT_TOLERANCE_S


@pytest.mark.parametrize(
    "evaluator",
    [
        parabola,
        lambda time: (
            10 + (seconds(time) - 6.2) * (15.3 - seconds(time)) * (1 + 0.01 * seconds(time))
        ),
    ],
    ids=["parabola", "asymmetric-cubic"],
)
def test_five_vs_one_second_grid_convergence_when_both_detect(evaluator) -> None:
    coarse = solve(evaluator, step=5)
    fine = solve(evaluator, step=1)
    assert len(coarse) == len(fine) == 1  # Counts must agree before pairing events.
    assert abs((coarse[0].start - fine[0].start).to_value(u.s)) <= 0.1
    assert abs((coarse[0].end - fine[0].end).to_value(u.s)) <= 0.1
    assert (
        abs((coarse[0].max_elevation_time - fine[0].max_elevation_time).to_value(u.s))
        <= PEAK_TIME_LIMIT_S
    )
    assert abs(coarse[0].max_elevation_deg - fine[0].max_elevation_deg) <= (
        PEAK_ELEVATION_LIMIT_DEG
    )


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"coarse_step_s": 0}, "coarse_step_s"),
        ({"coarse_step_s": -1}, "coarse_step_s"),
        ({"minimum_elevation_deg": float("inf")}, "minimum_elevation_deg"),
        ({"root_tolerance_s": 0}, "root_tolerance_s"),
        ({"root_tolerance_s": -0.1}, "root_tolerance_s"),
    ],
)
def test_invalid_numerical_settings(kwargs, message) -> None:
    with pytest.raises(ValueError, match=message):
        settings = {"minimum_elevation_deg": 10, **kwargs}
        find_access_windows(parabola, at(0), at(20), **settings)


def test_invalid_interval_and_ambiguous_time() -> None:
    with pytest.raises(ValueError, match="after start"):
        solve(begin=20, finish=0)
    with pytest.raises(ValueError, match="after start"):
        solve(begin=0, finish=0)
    with pytest.raises(TypeError, match="scalar astropy.time.Time in UTC"):
        find_access_windows(parabola, "2000-06-27", at(20), minimum_elevation_deg=10)
    with pytest.raises(TypeError, match="scalar astropy.time.Time in UTC"):
        find_access_windows(parabola, START.tai, at(20), minimum_elevation_deg=10)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_elevation_aborts_instead_of_returning_no_access(bad) -> None:
    with pytest.raises(ValueError, match="evaluated elevation"):
        solve(lambda _: bad)


def test_nonfinite_peak_evaluation_aborts_instead_of_returning_a_window() -> None:
    def sampled_only(time: Time) -> float:
        on_grid = abs(seconds(time) / 5.0 - round(seconds(time) / 5.0)) < 1e-9
        return 20.0 if on_grid else float("nan")

    with pytest.raises(ValueError, match="evaluated elevation"):
        solve(sampled_only)


def test_access_window_rejects_reversed_endpoints() -> None:
    first, last = at(1), at(0)
    with pytest.raises(ValueError, match="must not precede"):
        AccessWindow(first.jd1, first.jd2, last.jd1, last.jd2, first.jd1, first.jd2, 12.0)


def test_direct_zero_duration_window_and_invalid_peak_metadata() -> None:
    instant = at(1)
    point = AccessWindow(
        instant.jd1, instant.jd2, instant.jd1, instant.jd2, instant.jd1, instant.jd2, 12.0
    )
    assert point.duration_s == 0.0
    assert point.max_elevation_time == instant
    with pytest.raises(ValueError, match="within the access window"):
        AccessWindow(at(0).jd1, at(0).jd2, at(1).jd1, at(1).jd2, at(2).jd1, at(2).jd2, 12.0)
    with pytest.raises(ValueError, match="max_elevation_deg"):
        AccessWindow(
            instant.jd1,
            instant.jd2,
            instant.jd1,
            instant.jd2,
            instant.jd1,
            instant.jd2,
            float("nan"),
        )
