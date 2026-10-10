"""SGP4 propagation of archived TLE mean elements into TEME state vectors."""

from dataclasses import dataclass, field
from math import isfinite

from astropy.time import Time
from sgp4.api import SGP4_ERRORS, WGS72, Satrec
from sgp4.earth_gravity import wgs72
from sgp4.io import twoline2rv as validate_tle_format
from sgp4.io import verify_checksum


@dataclass(frozen=True, slots=True)
class TleRecord:
    """Original fixed-width TLE lines and their parsed UTC epoch."""

    line1: str
    line2: str
    source: str | None = None
    _epoch_jd1: float = field(init=False, repr=False)
    _epoch_jd2: float = field(init=False, repr=False)
    catalog_id: int = field(init=False)

    @property
    def epoch(self) -> Time:
        """Return a fresh UTC Time so the frozen record cannot be mutated through it."""
        return Time(self._epoch_jd1, self._epoch_jd2, format="jd", scale="utc")

    def __post_init__(self) -> None:
        for number, line in ((1, self.line1), (2, self.line2)):
            if not isinstance(line, str) or len(line) != 69 or not line.startswith(f"{number} "):
                raise ValueError(f"TLE line {number} must be an unmodified 69-character line")
            try:
                line.encode("ascii")
                verify_checksum(line)
            except (UnicodeEncodeError, ValueError) as exc:
                raise ValueError(
                    f"TLE line {number} is not valid ASCII with a valid checksum"
                ) from exc
        if self.line1[2:7] != self.line2[2:7]:
            raise ValueError("TLE catalogue identifiers on lines 1 and 2 differ")

        try:
            # The accelerated parser is permissive about malformed numeric fields.
            validate_tle_format(self.line1, self.line2, wgs72)
            satellite = Satrec.twoline2rv(self.line1, self.line2, WGS72)
        except (ValueError, TypeError) as exc:
            raise ValueError("TLE could not be parsed by SGP4") from exc

        object.__setattr__(self, "_epoch_jd1", satellite.jdsatepoch)
        object.__setattr__(self, "_epoch_jd2", satellite.jdsatepochF)
        object.__setattr__(self, "catalog_id", satellite.satnum)

    @classmethod
    def from_lines(cls, line1: str, line2: str, *, source: str | None = None) -> "TleRecord":
        return cls(line1, line2, source)


@dataclass(frozen=True, slots=True)
class TemeState:
    """SGP4 TEME position in km and velocity in km/s at scalar UTC time."""

    _time_jd1: float
    _time_jd2: float
    position_km: tuple[float, float, float]
    velocity_km_s: tuple[float, float, float]

    @property
    def time(self) -> Time:
        """Return a fresh UTC Time so the frozen state cannot be mutated through it."""
        return Time(self._time_jd1, self._time_jd2, format="jd", scale="utc")


class PropagationError(RuntimeError):
    """SGP4 returned an error instead of a usable TEME state."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"SGP4 error {code}: {message}")


class Sgp4Propagator:
    """Propagate one archived TLE with explicit WGS72 constants."""

    def __init__(self, tle: TleRecord) -> None:
        if not isinstance(tle, TleRecord):
            raise TypeError("tle must be a TleRecord")
        self.tle = tle
        self._satellite = Satrec.twoline2rv(tle.line1, tle.line2, WGS72)

    def propagate(self, time: Time) -> TemeState:
        if not isinstance(time, Time) or not time.isscalar or time.scale != "utc":
            raise TypeError("time must be a scalar astropy.time.Time in UTC")

        error, position, velocity = self._satellite.sgp4(time.jd1, time.jd2)
        if error:
            raise PropagationError(error, SGP4_ERRORS.get(error, "Unknown SGP4 error"))

        position_km = tuple(float(value) for value in position)
        velocity_km_s = tuple(float(value) for value in velocity)
        if (
            len(position_km) != 3
            or len(velocity_km_s) != 3
            or not all(isfinite(value) for value in (*position_km, *velocity_km_s))
        ):
            raise PropagationError(0, "SGP4 returned a non-finite or incomplete state")

        return TemeState(time.jd1, time.jd2, position_km, velocity_km_s)
