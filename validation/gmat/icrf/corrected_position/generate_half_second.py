"""Generate the frozen 0.5 s validation-only ICRF transfer file."""

import json
from hashlib import sha256
from pathlib import Path

import astropy.units as u
from astropy.time import Time
from astropy.utils import iers

from spacecraft_mission_analysis.input import load_analysis_config
from spacecraft_mission_analysis.orbit import Sgp4Propagator
from validation.gmat.icrf.check_transfer import CONFIG, _astropy_gcrs

HERE = Path(__file__).resolve().parent
ICRF_DIR = HERE.parent
EPHEMERIS = HERE / "vanguard_icrf_0p5s.e"
MANIFEST = HERE / "half_second_manifest.json"
START = Time("2000-06-27T19:59:00", format="isot", scale="utc")
SAMPLES = 5041


def main() -> None:
    first = json.loads((ICRF_DIR / "ephemeris_manifest.json").read_text(encoding="utf-8"))
    one_second = ICRF_DIR / first["file"]
    if sha256(one_second.read_bytes()).hexdigest() != first["sha256"]:
        raise RuntimeError("The established 1 s transfer file changed")
    conversion = json.loads((ICRF_DIR / "transfer_check.json").read_text(encoding="utf-8"))
    if conversion["status"] != "PASS":
        raise RuntimeError("Independent transfer conversion did not pass")
    config = load_analysis_config(CONFIG)
    if conversion["config_sha256"] != sha256(CONFIG.read_bytes()).hexdigest():
        raise RuntimeError("Canonical config changed after transfer check")
    if conversion["eop_table_sha256"] != config.earth_orientation.table_sha256:
        raise RuntimeError("EOP input changed after transfer check")
    propagator = Sgp4Propagator(config.tle)
    lines = [
        "stk.v.10.0",
        "BEGIN Ephemeris",
        f"NumberOfEphemerisPoints {SAMPLES}",
        "ScenarioEpoch 27 Jun 2000 19:59:00.000",
        "CentralBody Earth",
        "CoordinateSystem ICRF",
        "DistanceUnit Kilometers",
        "",
        "EphemerisTimePosVel",
    ]
    with (
        iers.conf.set_temp("auto_download", False),
        iers.earth_orientation_table.set(config.earth_orientation.build_table()),
    ):
        for index in range(SAMPLES):
            offset_s = index / 2
            time = START + offset_s * u.s
            position, velocity = _astropy_gcrs(propagator, time)
            values = " ".join(f"{value:.17e}" for value in (*position, *velocity))
            lines.append(f"{offset_s:.9f} {values}")
    lines.extend(("END Ephemeris", ""))
    EPHEMERIS.write_text("\n".join(lines), encoding="ascii", newline="\n")
    manifest = {
        "file": EPHEMERIS.name,
        "sha256": sha256(EPHEMERIS.read_bytes()).hexdigest(),
        "generator_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "one_second_sha256": first["sha256"],
        "conversion_result_sha256": sha256(
            (ICRF_DIR / "transfer_check.json").read_bytes()
        ).hexdigest(),
        "config_sha256": conversion["config_sha256"],
        "eop_table_sha256": config.earth_orientation.table_sha256,
        "samples": SAMPLES,
        "sampling_s": 0.5,
        "first_utc": "2000-06-27T19:59:00Z",
        "last_utc": "2000-06-27T20:41:00Z",
        "source": "Production WGS72 SGP4 TEME to validation-only Astropy GCRS",
        "stk_coordinate_system": "ICRF",
        "gcrs_to_stk_icrf": "Provisional geocentric ICRS-aligned transfer convention",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{EPHEMERIS} sha256={manifest['sha256']}")


if __name__ == "__main__":
    main()
