"""Hand-calculated, geometry-independent MA-08 interval fixtures."""

from dataclasses import FrozenInstanceError

import astropy.units as u
import pytest
from astropy.time import Time

from spacecraft_mission_analysis import CoverageInterval, compute_temporal_coverage

BASE = Time("2000-01-01T00:00:00", scale="utc")
# Integer-second UTC arithmetic is checked to 1 ns, well above the split-JD
# rounding floor and far below any physical event-detection accuracy claim.
SECONDS_ATOL = 1e-9
FRACTION_ATOL = 1e-12


def at(offset_s: int) -> Time:
    return BASE + offset_s * u.s


def interval(start_s: int, end_s: int) -> CoverageInterval:
    return CoverageInterval.from_times(at(start_s), at(end_s))


# Literal expected results were calculated by hand, independent of the union code.
# Each row: label, raw inputs, merged union, duration, fraction, count, longest gap.
CASES = [
    ("A no access", [], [], 0, 0.0, 0, (0, 100)),
    ("B full access", [(-10, 110)], [(0, 100)], 100, 1.0, 1, None),
    ("C one interval", [(20, 40)], [(20, 40)], 20, 0.2, 1, (40, 100)),
    (
        "D disjoint",
        [(10, 20), (40, 50), (70, 90)],
        [(10, 20), (40, 50), (70, 90)],
        40,
        0.4,
        3,
        (20, 40),
    ),
    ("E overlapping stations", [(10, 40), (30, 60)], [(10, 60)], 50, 0.5, 1, (60, 100)),
    ("F nested", [(10, 80), (20, 30), (50, 70)], [(10, 80)], 70, 0.7, 1, (80, 100)),
    ("G touching", [(10, 20), (20, 30)], [(10, 30)], 20, 0.2, 1, (30, 100)),
    (
        "H unsorted",
        [(70, 90), (10, 20), (40, 50)],
        [(10, 20), (40, 50), (70, 90)],
        40,
        0.4,
        3,
        (20, 40),
    ),
    (
        "I clipped both bounds",
        [(-20, 10), (90, 120)],
        [(0, 10), (90, 100)],
        20,
        0.2,
        2,
        (10, 90),
    ),
    ("J duplicate", [(10, 40), (10, 40)], [(10, 40)], 30, 0.3, 1, (40, 100)),
    (
        "K clip-overlap chain",
        [(-10, 15), (10, 35), (30, 50), (60, 80), (75, 120)],
        [(0, 50), (60, 100)],
        90,
        0.9,
        2,
        (50, 60),
    ),
]


@pytest.mark.parametrize(
    (
        "label",
        "raw",
        "expected_union",
        "expected_duration",
        "expected_fraction",
        "expected_count",
        "expected_gap",
    ),
    CASES,
    ids=[case[0] for case in CASES],
)
def test_hand_calculated_coverage(
    label,
    raw,
    expected_union,
    expected_duration,
    expected_fraction,
    expected_count,
    expected_gap,
) -> None:
    del label
    result = compute_temporal_coverage(at(0), at(100), [interval(*pair) for pair in raw])
    observed_union = [
        (
            float((item.start - BASE).to_value(u.s)),
            float((item.end - BASE).to_value(u.s)),
        )
        for item in result.union_intervals
    ]
    assert len(observed_union) == len(expected_union)
    for observed, expected in zip(observed_union, expected_union):
        assert observed == pytest.approx(expected, abs=SECONDS_ATOL)
    assert result.total_access_duration_s == pytest.approx(expected_duration, abs=SECONDS_ATOL)
    assert result.coverage_fraction == pytest.approx(expected_fraction, abs=FRACTION_ATOL)
    assert result.access_window_count == expected_count
    expected_gap_s = 0 if expected_gap is None else expected_gap[1] - expected_gap[0]
    assert result.longest_no_access_gap_s == pytest.approx(expected_gap_s, abs=SECONDS_ATOL)
    if expected_gap is None:
        assert result.longest_no_access_gap is None
    else:
        assert result.longest_no_access_gap is not None
        assert (
            float((result.longest_no_access_gap.start - BASE).to_value(u.s)),
            float((result.longest_no_access_gap.end - BASE).to_value(u.s)),
        ) == pytest.approx(expected_gap, abs=SECONDS_ATOL)


@pytest.mark.parametrize("end_s", [0, -1])
def test_nonpositive_analysis_span_rejected(end_s: int) -> None:
    with pytest.raises(ValueError, match="analysis end must be after start"):
        compute_temporal_coverage(at(0), at(end_s), [])


def test_reversed_source_interval_rejected() -> None:
    with pytest.raises(ValueError, match="interval end must not precede start"):
        interval(20, 10)


@pytest.mark.parametrize("invalid", ["2000-01-01", at(0).to_datetime()])
def test_ambiguous_time_type_rejected(invalid) -> None:
    with pytest.raises(TypeError, match="astropy.time.Time in UTC"):
        compute_temporal_coverage(invalid, at(100), [])
    with pytest.raises(TypeError, match="astropy.time.Time in UTC"):
        CoverageInterval.from_times(invalid, at(10))


def test_non_utc_and_vector_time_rejected() -> None:
    for invalid in (Time("2000-01-01", scale="tai"), Time(["2000-01-01"], scale="utc")):
        with pytest.raises(TypeError, match="astropy.time.Time in UTC"):
            compute_temporal_coverage(invalid, at(100), [])


def test_incompatible_interval_rejected() -> None:
    with pytest.raises(TypeError, match="CoverageInterval or AccessWindow"):
        compute_temporal_coverage(at(0), at(100), [(10, 20)])


def test_isolated_endpoint_has_zero_coverage_and_result_is_immutable() -> None:
    result = compute_temporal_coverage(at(0), at(100), [interval(-10, 0), interval(100, 110)])
    assert result.total_access_duration_s == 0
    assert result.access_window_count == 0
    with pytest.raises(FrozenInstanceError):
        result.coverage_fraction = 0.5
