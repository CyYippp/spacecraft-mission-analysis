"""Two explicit Earth-orientation input modes for scientific runs."""

from dataclasses import dataclass

import astropy.units as u
from astropy.utils import iers


@dataclass(frozen=True, slots=True)
class EarthOrientationConfig:
    """Configured IERS, or a frozen table loaded from an archived input file."""

    mode: str
    source: str
    table_identity: str | None = None
    table_sha256: str | None = None
    rows: tuple[tuple[int, float, float, float], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("Earth-orientation source must be a nonempty label")
        if self.mode == "configured_iers":
            if self.table_identity is not None or self.table_sha256 is not None or self.rows:
                raise ValueError("configured_iers cannot include an explicit table")
        elif self.mode == "explicit_table":
            if not self.table_identity or not self.table_sha256 or len(self.rows) < 2:
                raise ValueError("explicit_table requires identity, SHA-256 and at least two rows")
        else:
            raise ValueError("Earth-orientation mode must be configured_iers or explicit_table")

    def build_table(self) -> iers.IERS:
        """Construct a fresh Astropy IERS table from the frozen input snapshot."""
        if self.mode != "explicit_table":
            raise ValueError("configured_iers has no explicit table")
        return iers.IERS(
            {
                "MJD": [row[0] for row in self.rows] * u.day,
                "UT1_UTC": [row[1] for row in self.rows] * u.s,
                "PM_x": [row[2] for row in self.rows] * u.arcsec,
                "PM_y": [row[3] for row in self.rows] * u.arcsec,
            }
        )
