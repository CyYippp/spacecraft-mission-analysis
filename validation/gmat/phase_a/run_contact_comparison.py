"""One-shot GMAT Phase A contact comparison on the qualified ICRF transfer."""

import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import astropy.units as u
from astropy.time import Time

from validation.gmat.icrf.check_transfer import CONFIG

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
ICRF_DIR = HERE.parent / "icrf"
GMAT_BIN = Path(r"C:\Users\Cyrus\Applications\GMAT\R2026a\bin")
GMAT_DATA = GMAT_BIN.parent / "data"
PRODUCTION_RESULT = ROOT / "examples" / "vanguard_run" / "run.json"
EPOCH_START = "27 Jun 2000 20:00:00.000"
EPOCH_END = "27 Jun 2000 20:40:00.000"
TIME_LIMIT_S = 0.25
DURATION_LIMIT_S = 0.50
EVENT_SHIFT_LIMIT_S = 0.02
OBSERVER_NAMES = {
    "Greenwich": "Equator Greenwich synthetic fixed WGS84 station",
    "OneNorthOneEast": "Synthetic 1N 1E WGS84 station",
}
EVENT_LINE = re.compile(
    r"^\s*(\d{1,2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2}\.\d+)\s+"
    r"(\d{1,2} [A-Za-z]{3} \d{4} \d{2}:\d{2}:\d{2}\.\d+)\s+"
    r"([+-]?\d+(?:\.\d+)?)\s*$"
)


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _time(text: str) -> Time:
    if text.endswith("Z"):
        return Time(text[:-1], format="isot", scale="utc")
    return Time(datetime.strptime(text, "%d %b %Y %H:%M:%S.%f").replace(tzinfo=timezone.utc))


def _ephemeris(mode: str) -> tuple[Path, dict]:
    if mode == "1s":
        manifest = json.loads((ICRF_DIR / "ephemeris_manifest.json").read_text(encoding="utf-8"))
        path = ICRF_DIR / manifest["file"]
    elif mode == "0p5s":
        manifest = json.loads(
            (ICRF_DIR / "corrected_position" / "half_second_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        path = ICRF_DIR / "corrected_position" / manifest["file"]
        one_second = json.loads((HERE / "phase_a_1s.json").read_text(encoding="utf-8"))
        if one_second["status"] != "PASS":
            raise RuntimeError("1 s Phase A event comparison has not passed")
    else:
        raise ValueError("mode must be 1s or 0p5s")
    if _hash(path) != manifest["sha256"]:
        raise RuntimeError("Transfer ephemeris changed after its generation")
    return path, manifest


def _write_script(ephemeris: Path, script: Path, report: Path) -> None:
    pck = GMAT_DATA / "planetary_coeff" / "SPICEPlanetaryConstantsKernel.tpc"
    lines = [
        f"SolarSystem.PCKFilename = '{pck.as_posix()}';",
        "Earth.EquatorialRadius = 6378.1366;",
        "Earth.Flattening = 0.00335281310845547;",
        "Create Spacecraft ImportedVanguard;",
        "ImportedVanguard.DateFormat = UTCGregorian;",
        "ImportedVanguard.Epoch = '27 Jun 2000 19:59:00.000';",
        f"ImportedVanguard.EphemerisName = '{ephemeris.as_posix()}';",
        "Create Propagator ImportedSTK;",
        "ImportedSTK.Type = STK;",
        "ImportedSTK.StepSize = 1;",
        "ImportedSTK.CentralBody = Earth;",
        "ImportedSTK.EpochFormat = A1ModJulian;",
        "ImportedSTK.StartEpoch = 'FromSpacecraft';",
    ]
    for resource, latitude, longitude in (("Greenwich", 0, 0), ("OneNorthOneEast", 1, 1)):
        lines.extend(
            (
                f"Create GroundStation {resource};",
                f"{resource}.CentralBody = Earth;",
                f"{resource}.StateType = Spherical;",
                f"{resource}.HorizonReference = Ellipsoid;",
                f"{resource}.Location1 = {latitude};",
                f"{resource}.Location2 = {longitude};",
                f"{resource}.Location3 = 0;",
                f"{resource}.DataSource = Constant;",
                f"{resource}.MinimumElevationAngle = 10;",
            )
        )
    lines.extend(
        (
            "Create ContactLocator VanguardContacts;",
            "VanguardContacts.Target = ImportedVanguard;",
            "VanguardContacts.Observers = {Greenwich, OneNorthOneEast};",
            f"VanguardContacts.Filename = '{report.as_posix()}';",
            "VanguardContacts.InputEpochFormat = 'UTCGregorian';",
            f"VanguardContacts.InitialEpoch = '{EPOCH_START}';",
            f"VanguardContacts.FinalEpoch = '{EPOCH_END}';",
            "VanguardContacts.UseEntireInterval = false;",
            "VanguardContacts.UseLightTimeDelay = false;",
            "VanguardContacts.UseStellarAberration = false;",
            "VanguardContacts.StepSize = 1;",
            "VanguardContacts.RunMode = Manual;",
            "VanguardContacts.WriteReport = true;",
            "VanguardContacts.ReportFormat = 'Legacy';",
            "VanguardContacts.ReportTimeFormat = 'UTCGregorian';",
            "Create Array initialState[6,1] finalState[6,1];",
            "Create String initialEpoch finalEpoch;",
            "BeginMissionSequence;",
            "[initialEpoch, initialState, finalEpoch, finalState] = "
            "GetEphemStates('STK', ImportedVanguard, 'UTCGregorian', EarthICRF);",
            "ImportedVanguard.UTCGregorian = initialEpoch;",
            "Propagate ImportedSTK(ImportedVanguard) {ImportedVanguard.ElapsedSecs = 2519};",
            "FindEvents VanguardContacts;",
        )
    )
    script.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _parse_report(path: Path) -> dict[str, list[dict]]:
    observations: dict[str, list[dict]] = {}
    reported_counts: dict[str, int] = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("Observer:"):
            current = line.partition(":")[2].strip()
            if current in observations:
                raise RuntimeError(f"Duplicate observer section: {current}")
            observations[current] = []
        elif current is not None:
            match = EVENT_LINE.fullmatch(line)
            if match:
                observations[current].append(
                    {"start_utc": match[1], "end_utc": match[2], "duration_s": float(match[3])}
                )
            count = re.fullmatch(r"\s*Number of events\s*:\s*(\d+)\s*", line)
            if count:
                reported_counts[current] = int(count[1])
    if set(observations) != set(OBSERVER_NAMES):
        raise RuntimeError(f"Unexpected GMAT observers: {list(observations)}")
    if set(reported_counts) != set(OBSERVER_NAMES):
        raise RuntimeError("GMAT report omitted one or more event counts")
    if any(reported_counts[name] != len(rows) for name, rows in observations.items()):
        raise RuntimeError("GMAT report count does not match parsed event rows")
    return observations


def _compare_production(gmat: dict[str, list[dict]]) -> tuple[list[dict], bool]:
    production = json.loads(PRODUCTION_RESULT.read_text(encoding="utf-8"))
    if production["status"] != "SUCCESS":
        raise RuntimeError("Archived production run is not successful")
    by_name = {row["station_name"]: row["windows"] for row in production["station_access"]}
    comparisons = []
    overall = True
    for observer, station in OBSERVER_NAMES.items():
        expected_windows = by_name[station]
        observed_windows = gmat[observer]
        same_count = len(expected_windows) == len(observed_windows)
        paired = []
        if same_count:
            for expected, observed in zip(expected_windows, observed_windows, strict=True):
                production_start = _time(expected["start_utc"])
                production_end = _time(expected["end_utc"])
                gmat_start = _time(observed["start_utc"])
                gmat_end = _time(observed["end_utc"])
                overlap = gmat_start < production_end and production_start < gmat_end
                signed_start = float((gmat_start - production_start).to_value(u.s))
                signed_end = float((gmat_end - production_end).to_value(u.s))
                signed_duration = observed["duration_s"] - expected["duration_s"]
                passed = (
                    overlap
                    and abs(signed_start) <= TIME_LIMIT_S
                    and abs(signed_end) <= TIME_LIMIT_S
                    and abs(signed_duration) <= DURATION_LIMIT_S
                )
                paired.append(
                    {
                        "production": expected,
                        "gmat": observed,
                        "intervals_overlap": overlap,
                        "gmat_minus_production_aos_s": signed_start,
                        "gmat_minus_production_los_s": signed_end,
                        "gmat_minus_production_duration_s": signed_duration,
                        "pass": passed,
                    }
                )
        station_pass = same_count and all(row["pass"] for row in paired)
        overall = overall and station_pass
        comparisons.append(
            {
                "observer": observer,
                "production_station": station,
                "production_event_count": len(expected_windows),
                "gmat_event_count": len(observed_windows),
                "same_count": same_count,
                "paired_by_chronological_order": paired,
                "pass": station_pass,
            }
        )
    return comparisons, overall


def _event_convergence(gmat: dict[str, list[dict]]) -> tuple[list[dict], bool]:
    earlier = json.loads((HERE / "phase_a_1s.json").read_text(encoding="utf-8"))
    reference = earlier["gmat_events"]
    comparisons = []
    overall = True
    for observer in OBSERVER_NAMES:
        first = reference[observer]
        second = gmat[observer]
        same_count = len(first) == len(second)
        events = []
        if same_count:
            for left, right in zip(first, second, strict=True):
                aos = float((_time(right["start_utc"]) - _time(left["start_utc"])).to_value(u.s))
                los = float((_time(right["end_utc"]) - _time(left["end_utc"])).to_value(u.s))
                overlap = _time(left["start_utc"]) < _time(right["end_utc"]) and _time(
                    right["start_utc"]
                ) < _time(left["end_utc"])
                passed = (
                    overlap and abs(aos) <= EVENT_SHIFT_LIMIT_S and abs(los) <= EVENT_SHIFT_LIMIT_S
                )
                events.append(
                    {
                        "half_second_minus_one_second_aos_s": aos,
                        "half_second_minus_one_second_los_s": los,
                        "intervals_overlap": overlap,
                        "pass": passed,
                    }
                )
        station_pass = same_count and all(row["pass"] for row in events)
        overall = overall and station_pass
        comparisons.append(
            {"observer": observer, "same_count": same_count, "events": events, "pass": station_pass}
        )
    return comparisons, overall


def _environment() -> dict:
    files = {
        "gmat_executable": GMAT_BIN / "GmatConsole.exe",
        "gmat_startup": GMAT_BIN / "gmat_startup_file.txt",
        "gmat_eop": GMAT_DATA / "planetary_coeff" / "eopc04_08.62-now",
        "gmat_pck": GMAT_DATA / "planetary_coeff" / "SPICEPlanetaryConstantsKernel.tpc",
        "gmat_lsk": GMAT_DATA / "time" / "SPICELeapSecondKernel.tls",
        "gmat_leap_seconds": GMAT_DATA / "time" / "tai-utc.dat",
    }
    return {
        "platform": platform.platform(),
        "gmat_release": "R2026a",
        "gmat_build_date": "Mar 26 2026 15:02:55",
        "gmat_invocation": "GmatConsole.exe --logfile <path> --exit --run <script>, cwd=GMAT bin",
        "files": {key: {"path": str(path), "sha256": _hash(path)} for key, path in files.items()},
        "core_earth_equatorial_radius_km": 6378.1366,
        "core_earth_flattening": 0.00335281310845547,
        "spice_pck_earth_radii_km": [6378.1366, 6378.1366, 6356.7519],
        "production_station_ellipsoid": "WGS84",
        "production_wgs84_equatorial_radius_km": 6378.137,
        "production_wgs84_flattening": 1 / 298.257223563,
        "station_geodetic_coordinates": {
            "Greenwich": {"latitude_deg": 0, "longitude_deg_east": 0, "height_km": 0},
            "OneNorthOneEast": {"latitude_deg": 1, "longitude_deg_east": 1, "height_km": 0},
        },
        "production_eop": "explicit synthetic zero UT1-UTC/xp/yp fixture",
        "contact_environment": "Installed GMAT SPICE PCK, BPC, LSK and startup EOP; no overrides",
    }


def main(mode: str) -> int:
    corrected = ICRF_DIR / "corrected_position"
    for gate in ("position_gate_1s.json", "position_gate_0p5s.json"):
        if json.loads((corrected / gate).read_text(encoding="utf-8"))["status"] != "PASS":
            raise RuntimeError(f"Corrected ICRF transfer gate {gate} has not passed")
    ephemeris, manifest = _ephemeris(mode)
    script = HERE / f"phase_a_{mode}.script"
    report = HERE / f"phase_a_{mode}_report.txt"
    stdout = HERE / f"phase_a_{mode}_stdout.txt"
    stderr = HERE / f"phase_a_{mode}_stderr.txt"
    log = HERE / f"phase_a_{mode}_log.txt"
    result = HERE / f"phase_a_{mode}.json"
    _write_script(ephemeris, script, report)
    completed = subprocess.run(
        [str(GMAT_BIN / "GmatConsole.exe"), "--logfile", str(log), "--exit", "--run", str(script)],
        cwd=GMAT_BIN,
        input="q\n",
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    stdout.write_text(completed.stdout, encoding="utf-8")
    stderr.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0 or "Mission run completed." not in completed.stdout:
        failure = {
            "status": "GMAT_EXECUTION_FAILED",
            "mode": mode,
            "gmat_returncode": completed.returncode,
            "script_sha256": _hash(script),
            "ephemeris_sha256": manifest["sha256"],
        }
        result.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        print(f"GMAT execution failed for {mode}; see {stdout} and {log}")
        return 2
    gmat = _parse_report(report)
    comparison, production_pass = _compare_production(gmat)
    convergence = None
    convergence_pass = True
    if mode == "0p5s":
        convergence, convergence_pass = _event_convergence(gmat)
    output = {
        "status": "PASS" if production_pass and convergence_pass else "FAIL",
        "mode": mode,
        "analysis_start_utc": "2000-06-27T20:00:00Z",
        "analysis_end_utc": "2000-06-27T20:40:00Z",
        "ephemeris_sha256": manifest["sha256"],
        "ephemeris_sampling_s": manifest["sampling_s"],
        "canonical_config_sha256": _hash(CONFIG),
        "archived_production_run_sha256": _hash(PRODUCTION_RESULT),
        "script_sha256": _hash(script),
        "raw_report_sha256": _hash(report),
        "gmat_returncode": completed.returncode,
        "environment": _environment(),
        "contact_settings": {
            "target": "ImportedVanguard",
            "observers": list(OBSERVER_NAMES),
            "horizon_reference": "Ellipsoid",
            "minimum_elevation_deg": 10,
            "step_size_s": 1,
            "use_entire_interval": False,
            "use_light_time_delay": False,
            "use_stellar_aberration": False,
            "extra_occulting_bodies": [],
            "run_mode": "Manual",
            "report_format": "Legacy UTCGregorian",
        },
        "criteria": {
            "same_event_count_and_order": True,
            "aos_los_abs_limit_s": TIME_LIMIT_S,
            "duration_abs_limit_s": DURATION_LIMIT_S,
            "one_second_vs_half_second_event_shift_limit_s": EVENT_SHIFT_LIMIT_S,
        },
        "gmat_events": gmat,
        "production_comparison": comparison,
        "production_criteria_pass": production_pass,
        "event_convergence": convergence,
        "event_convergence_pass": convergence_pass,
    }
    result.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"{mode} {output['status']}: {result}")
    for station in comparison:
        print(
            f"{station['observer']} production={station['production_event_count']} "
            f"GMAT={station['gmat_event_count']} pass={station['pass']}"
        )
        for row in station["paired_by_chronological_order"]:
            print(
                f"  GMAT-production AOS={row['gmat_minus_production_aos_s']:.9f} s "
                f"LOS={row['gmat_minus_production_los_s']:.9f} s "
                f"duration={row['gmat_minus_production_duration_s']:.9f} s"
            )
    if convergence is not None:
        for station in convergence:
            for row in station["events"]:
                print(
                    f"{station['observer']} 0.5s-1s AOS="
                    f"{row['half_second_minus_one_second_aos_s']:.9f} s "
                    f"LOS={row['half_second_minus_one_second_los_s']:.9f} s"
                )
    return 0 if output["status"] == "PASS" else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m validation.gmat.phase_a.run_contact_comparison 1s|0p5s")
    raise SystemExit(main(sys.argv[1]))
