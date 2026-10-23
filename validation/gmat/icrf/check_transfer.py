"""Frozen validation-only Astropy TEME→GCRS versus Skyfield transfer check."""

import json
from datetime import timezone
from hashlib import sha256
from math import sqrt
from pathlib import Path

import astropy
import astropy.units as u
import sgp4
import skyfield
from astropy.coordinates import GCRS, TEME, CartesianDifferential, CartesianRepresentation
from astropy.time import Time
from astropy.utils import iers
from skyfield.api import EarthSatellite, load

from spacecraft_mission_analysis.input import load_analysis_config
from spacecraft_mission_analysis.orbit import Sgp4Propagator

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "examples" / "vanguard_run" / "config.json"
OUTPUT = Path(__file__).with_name("transfer_check.json")
EPOCHS = (
    "2000-06-27T19:59:00",
    "2000-06-27T20:00:00",
    "2000-06-27T20:20:00",
    "2000-06-27T20:40:00",
    "2000-06-27T20:41:00",
)
POSITION_LIMIT_KM = 0.001
VELOCITY_LIMIT_KM_S = 1e-6


def _norm(values: list[float]) -> float:
    return sqrt(sum(value * value for value in values))


def _astropy_gcrs(propagator: Sgp4Propagator, time: Time) -> tuple[list[float], list[float]]:
    state = propagator.propagate(time)
    position = CartesianRepresentation(u.Quantity(state.position_km, u.km))
    velocity = CartesianDifferential(u.Quantity(state.velocity_km_s, u.km / u.s))
    teme = TEME(position.with_differentials(velocity), obstime=time)
    gcrs = teme.transform_to(GCRS(obstime=time))
    return (
        [float(value) for value in gcrs.cartesian.xyz.to_value(u.km)],
        [float(value) for value in gcrs.cartesian.differentials["s"].d_xyz.to_value(u.km / u.s)],
    )


def main() -> int:
    config = load_analysis_config(CONFIG)
    assert config.earth_orientation.mode == "explicit_table"
    propagator = Sgp4Propagator(config.tle)
    timescale = load.timescale(builtin=True)
    satellite = EarthSatellite(config.tle.line1, config.tle.line2, ts=timescale)
    rows = []
    with (
        iers.conf.set_temp("auto_download", False),
        iers.earth_orientation_table.set(config.earth_orientation.build_table()),
    ):
        for epoch in EPOCHS:
            time = Time(epoch, format="isot", scale="utc")
            astropy_position, astropy_velocity = _astropy_gcrs(propagator, time)
            skyfield_state = satellite.at(
                timescale.from_datetime(time.to_datetime(timezone=timezone.utc))
            )
            skyfield_position = [float(value) for value in skyfield_state.position.km]
            skyfield_velocity = [float(value) for value in skyfield_state.velocity.km_per_s]
            position_delta = [
                left - right
                for left, right in zip(astropy_position, skyfield_position, strict=True)
            ]
            velocity_delta = [
                left - right
                for left, right in zip(astropy_velocity, skyfield_velocity, strict=True)
            ]
            position_norm = _norm(position_delta)
            velocity_norm = _norm(velocity_delta)
            rows.append(
                {
                    "utc": f"{epoch}Z",
                    "astropy_gcrs_position_km": astropy_position,
                    "astropy_gcrs_velocity_km_s": astropy_velocity,
                    "skyfield_geocentric_position_km": skyfield_position,
                    "skyfield_geocentric_velocity_km_s": skyfield_velocity,
                    "astropy_minus_skyfield_position_km": position_delta,
                    "astropy_minus_skyfield_velocity_km_s": velocity_delta,
                    "position_residual_norm_km": position_norm,
                    "velocity_residual_norm_km_s": velocity_norm,
                    "pass": position_norm <= POSITION_LIMIT_KM
                    and velocity_norm <= VELOCITY_LIMIT_KM_S,
                }
            )

    report = {
        "protocol": "PROTOCOL.md, frozen before comparison",
        "status": "PASS" if all(row["pass"] for row in rows) else "FAIL",
        "position_limit_km": POSITION_LIMIT_KM,
        "velocity_limit_km_s": VELOCITY_LIMIT_KM_S,
        "convention": "Astropy TEME to GCRS using canonical explicit EOP; Skyfield geocentric inertial",
        "shared_sgp4_kernel": True,
        "config_sha256": sha256(CONFIG.read_bytes()).hexdigest(),
        "eop_table_identity": config.earth_orientation.table_identity,
        "eop_table_sha256": config.earth_orientation.table_sha256,
        "tle_lines": [config.tle.line1, config.tle.line2],
        "versions": {
            "astropy": astropy.__version__,
            "skyfield": skyfield.__version__,
            "sgp4": sgp4.__version__,
        },
        "samples": rows,
    }
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: {OUTPUT}")
    for row in rows:
        print(
            f"{row['utc']} position={row['position_residual_norm_km']:.12g} km "
            f"velocity={row['velocity_residual_norm_km_s']:.12g} km/s "
            f"{'PASS' if row['pass'] else 'FAIL'}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
