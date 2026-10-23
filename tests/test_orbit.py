"""Vallado/python-sgp4 case 00005; see fixtures/sgp4/README.md."""

import json
from dataclasses import FrozenInstanceError
from datetime import datetime
from math import isclose, isfinite
from pathlib import Path

import pytest
from astropy.time import Time
from sgp4.api import SGP4_ERRORS
from sgp4.io import fix_checksum

from spacecraft_mission_analysis import (
    PropagationError,
    Sgp4Propagator,
    TemeState,
    TleRecord,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "sgp4" / "vanguard_1_00005.json").read_text(
        encoding="utf-8"
    )
)
LINE1 = FIXTURE["tle_line1"]
LINE2 = FIXTURE["tle_line2"]
EXPECTED_POSITION_KM = FIXTURE["expected_position_km"]
EXPECTED_VELOCITY_KM_S = FIXTURE["expected_velocity_km_s"]

# The upstream file prints position to 1e-8 km and velocity to 1e-9 km/s.
# Allow its last-place rounding plus the small C++/JD-path differences that
# python-sgp4 itself permits (2e-7 in its tcppver test); thresholds fixed here
# before observing this adapter's residuals.
POSITION_TOLERANCE_KM = 2e-7
VELOCITY_TOLERANCE_KM_S = 2e-9
# Split-JD arithmetic should reproduce a minute offset to well below a microsecond.
EPOCH_OFFSET_TOLERANCE_MIN = 1e-9


@pytest.fixture
def tle() -> TleRecord:
    return TleRecord.from_lines(LINE1, LINE2, source=FIXTURE["case"])


def test_vallado_reference_vector_and_teme_contract(tle: TleRecord) -> None:
    time = Time(
        tle.epoch.jd1,
        tle.epoch.jd2 + FIXTURE["minutes_since_epoch"] / 1440,
        format="jd",
        scale="utc",
    )
    state = Sgp4Propagator(tle).propagate(time)

    position_residuals = tuple(a - e for a, e in zip(state.position_km, EXPECTED_POSITION_KM))
    velocity_residuals = tuple(a - e for a, e in zip(state.velocity_km_s, EXPECTED_VELOCITY_KM_S))

    assert isinstance(state, TemeState)
    assert state.time.scale == "utc"
    assert state.time == time
    assert len(state.position_km) == len(state.velocity_km_s) == 3
    assert all(isfinite(value) for value in (*state.position_km, *state.velocity_km_s))
    assert isclose(
        state.minutes_since_tle_epoch,
        FIXTURE["minutes_since_epoch"],
        rel_tol=0,
        abs_tol=EPOCH_OFFSET_TOLERANCE_MIN,
    )
    assert max(map(abs, position_residuals)) <= POSITION_TOLERANCE_KM
    assert max(map(abs, velocity_residuals)) <= VELOCITY_TOLERANCE_KM_S
    returned_time = state.time
    returned_time.format = "mjd"
    assert state.time.format == "jd"
    with pytest.raises(FrozenInstanceError):
        state.minutes_since_tle_epoch = 0.0  # type: ignore[misc]


@pytest.mark.parametrize("offset_min", [0.0, -30.0])
def test_signed_sgp4_epoch_offset(tle: TleRecord, offset_min: float) -> None:
    time = Time(
        tle.epoch.jd1,
        tle.epoch.jd2 + offset_min / 1440.0,
        format="jd",
        scale="utc",
    )
    state = Sgp4Propagator(tle).propagate(time)
    assert isclose(
        state.minutes_since_tle_epoch,
        offset_min,
        rel_tol=0,
        abs_tol=EPOCH_OFFSET_TOLERANCE_MIN,
    )


def test_original_tle_and_epoch_are_preserved(tle: TleRecord) -> None:
    assert (tle.line1, tle.line2) == (LINE1, LINE2)
    assert tle.catalog_id == FIXTURE["catalog_id"]
    assert tle.source == FIXTURE["case"]
    assert tle.epoch.scale == "utc"
    returned_epoch = tle.epoch
    returned_epoch.format = "mjd"
    assert tle.epoch.format == "jd"
    with pytest.raises(FrozenInstanceError):
        tle.line1 = "changed"  # type: ignore[misc]


def test_bad_checksum_and_mismatched_catalogue_are_rejected() -> None:
    with pytest.raises(ValueError, match="checksum"):
        TleRecord.from_lines(LINE1[:-1] + "0", LINE2)
    with pytest.raises(ValueError, match="catalogue identifiers"):
        TleRecord.from_lines(LINE1, fix_checksum("2 00006" + LINE2[7:]))
    with pytest.raises(ValueError, match="parsed by SGP4"):
        TleRecord.from_lines(LINE1, fix_checksum(LINE2[:8] + "x" + LINE2[9:]))
    with pytest.raises(ValueError, match="parsed by SGP4"):
        TleRecord(LINE1, fix_checksum(LINE2[:8] + "x" + LINE2[9:]))


@pytest.mark.parametrize(
    "bad_time",
    [
        datetime(2000, 6, 28, 0, 50, 19),  # naive datetime
        "2000-06-28T00:50:19",
        Time("2000-06-28T00:50:19", scale="tai"),
        Time(["2000-06-28T00:50:19"], scale="utc"),
    ],
)
def test_propagation_rejects_ambiguous_or_non_scalar_time(tle: TleRecord, bad_time: object) -> None:
    with pytest.raises(TypeError, match="scalar astropy.time.Time in UTC"):
        Sgp4Propagator(tle).propagate(bad_time)  # type: ignore[arg-type]


def test_sgp4_error_never_returns_a_state(tle: TleRecord) -> None:
    class FailedSatellite:
        def sgp4(self, jd1: float, jd2: float) -> tuple[int, tuple[float, ...], tuple[float, ...]]:
            return 6, (float("nan"),) * 3, (float("nan"),) * 3

    propagator = Sgp4Propagator(tle)
    propagator._satellite = FailedSatellite()  # type: ignore[assignment]
    with pytest.raises(PropagationError) as failure:
        propagator.propagate(tle.epoch)
    assert failure.value.code == 6
    assert failure.value.message == SGP4_ERRORS[6]
    assert "SGP4 error 6" in str(failure.value)
