"""Validation-only, gated GMAT numerical trajectory diagnostic."""

import csv
import json
import math
import re
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

from astropy.time import Time
from astropy.utils import iers

from spacecraft_mission_analysis.input import load_analysis_config
from spacecraft_mission_analysis.orbit import Sgp4Propagator
from validation.gmat.icrf.check_transfer import CONFIG, _astropy_gcrs
from validation.gmat.phase_a.run_contact_comparison import (
    GMAT_BIN,
    GMAT_DATA,
    PRODUCTION_RESULT,
    _time,
)
from validation.gmat.phase_a.run_contact_comparison import (
    _parse_report as parse_contacts,
)

HERE = Path(__file__).resolve().parent
GRAVITY = GMAT_DATA / "gravity" / "earth" / "EGM96.cof"
PCK = GMAT_DATA / "planetary_coeff" / "SPICEPlanetaryConstantsKernel.tpc"
EPOCH = "2000-06-27T20:00:00"
REPORT_FIELDS = (
    "Vanguard.UTCGregorian Vanguard.EarthICRF.X Vanguard.EarthICRF.Y "
    "Vanguard.EarthICRF.Z Vanguard.EarthICRF.VX Vanguard.EarthICRF.VY "
    "Vanguard.EarthICRF.VZ"
)
OFFSETS_MIN = tuple(range(0, 41, 5))
INITIAL_POSITION_LIMIT_KM = 1e-6
INITIAL_VELOCITY_LIMIT_KM_S = 1e-9
CONVERGENCE_POSITION_LIMIT_KM = 0.001
CONVERGENCE_VELOCITY_LIMIT_KM_S = 1e-6


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def record(path: Path, data: dict) -> None:
    write(path, json.dumps(data, indent=2) + "\n")


def norm(vector: list[float]) -> float:
    return math.sqrt(sum(x * x for x in vector))


def state_lines(initial: list[float]) -> list[str]:
    lines = [
        f"SolarSystem.PCKFilename = '{PCK.as_posix()}';",
        "Earth.EquatorialRadius = 6378.1366;",
        "Earth.Flattening = 0.00335281310845547;",
        "Create Spacecraft Vanguard;",
        "Vanguard.DateFormat = UTCGregorian;",
        "Vanguard.Epoch = '27 Jun 2000 20:00:00.000';",
        "Vanguard.CoordinateSystem = EarthICRF;",
        "Vanguard.DisplayStateType = Cartesian;",
    ]
    lines.extend(
        f"Vanguard.{field} = {value:.17g};"
        for field, value in zip(("X", "Y", "Z", "VX", "VY", "VZ"), initial, strict=True)
    )
    return lines


def report_lines(name: str, filename: Path) -> list[str]:
    return [
        f"Create ReportFile {name};",
        f"{name}.Filename = '{filename.as_posix()}';",
        f"{name}.Precision = 17;",
    ]


def force_lines(max_step: int) -> list[str]:
    return [
        "Create ForceModel EarthOnly;",
        "EarthOnly.CentralBody = Earth;",
        "EarthOnly.PrimaryBodies = {Earth};",
        "EarthOnly.PointMasses = {};",
        "EarthOnly.GravityField.Earth.PotentialFile = 'EGM96.cof';",
        "EarthOnly.GravityField.Earth.Degree = 4;",
        "EarthOnly.GravityField.Earth.Order = 4;",
        "EarthOnly.GravityField.Earth.TideModel = 'None';",
        "EarthOnly.Drag.AtmosphereModel = None;",
        "EarthOnly.SRP = Off;",
        "EarthOnly.RelativisticCorrection = Off;",
        "EarthOnly.ErrorControl = RSSStep;",
        "Create Propagator Numerical;",
        "Numerical.FM = EarthOnly;",
        "Numerical.Type = PrinceDormand78;",
        "Numerical.Accuracy = 1e-12;",
        "Numerical.InitialStepSize = 10;",
        "Numerical.MinStep = 0.001;",
        f"Numerical.MaxStep = {max_step};",
        "Numerical.StopIfAccuracyIsViolated = true;",
    ]


def station_lines() -> list[str]:
    lines = []
    for name, latitude, longitude in (("Greenwich", 0, 0), ("OneNorthOneEast", 1, 1)):
        lines.extend(
            (
                f"Create GroundStation {name};",
                f"{name}.CentralBody = Earth;",
                f"{name}.StateType = Spherical;",
                f"{name}.HorizonReference = Ellipsoid;",
                f"{name}.Location1 = {latitude};",
                f"{name}.Location2 = {longitude};",
                f"{name}.Location3 = 0;",
                f"{name}.DataSource = Constant;",
                f"{name}.MinimumElevationAngle = 10;",
            )
        )
    lines.extend(
        (
            "Create ContactLocator VanguardContacts;",
            "VanguardContacts.Target = Vanguard;",
            "VanguardContacts.Observers = {Greenwich, OneNorthOneEast};",
            f"VanguardContacts.Filename = '{(HERE / 'contacts_report.txt').as_posix()}';",
            "VanguardContacts.InputEpochFormat = 'UTCGregorian';",
            "VanguardContacts.InitialEpoch = '27 Jun 2000 20:00:00.000';",
            "VanguardContacts.FinalEpoch = '27 Jun 2000 20:40:00.000';",
            "VanguardContacts.UseEntireInterval = false;",
            "VanguardContacts.UseLightTimeDelay = false;",
            "VanguardContacts.UseStellarAberration = false;",
            "VanguardContacts.StepSize = 1;",
            "VanguardContacts.RunMode = Manual;",
            "VanguardContacts.WriteReport = true;",
            "VanguardContacts.ReportFormat = 'Legacy';",
            "VanguardContacts.ReportTimeFormat = 'UTCGregorian';",
        )
    )
    return lines


def script_lines(initial: list[float], stage: str) -> list[str]:
    lines = state_lines(initial)
    if stage == "gate":
        lines += report_lines("StateReport", HERE / "gate_report.txt")
        lines += ["BeginMissionSequence;", f"Report StateReport {REPORT_FIELDS};"]
        return lines
    lines += force_lines(30 if stage == "refined" else 60)
    if stage == "contacts":
        lines += station_lines()
    else:
        lines += report_lines("StateReport", HERE / f"{stage}_report.txt")
    lines.append("BeginMissionSequence;")
    if stage != "contacts":
        lines.append(f"Report StateReport {REPORT_FIELDS};")
    for _ in range(8):
        lines.append("Propagate Numerical(Vanguard) {Vanguard.ElapsedSecs = 300};")
        if stage != "contacts":
            lines.append(f"Report StateReport {REPORT_FIELDS};")
    if stage == "contacts":
        lines.append("FindEvents VanguardContacts;")
    return lines


def prepare() -> None:
    if (HERE / "prepared.json").exists():
        raise RuntimeError("Phase B setup already prepared; no regeneration allowed")
    config = load_analysis_config(CONFIG)
    if config.earth_orientation.mode != "explicit_table":
        raise RuntimeError("Canonical archived run must supply explicit EOP")
    transfer = json.loads((HERE.parent / "icrf" / "transfer_check.json").read_text())
    if transfer["status"] != "PASS" or transfer["config_sha256"] != digest(CONFIG):
        raise RuntimeError("Phase A transfer check or canonical config has changed")
    with (
        iers.conf.set_temp("auto_download", False),
        iers.earth_orientation_table.set(config.earth_orientation.build_table()),
    ):
        r, v = _astropy_gcrs(Sgp4Propagator(config.tle), Time(EPOCH, format="isot", scale="utc"))
    initial = r + v
    if not all(math.isfinite(value) for value in initial):
        raise RuntimeError("Nonfinite production-derived initial state")
    scripts = {}
    for stage in ("gate", "base", "refined", "contacts"):
        path = HERE / f"{stage}.script"
        write(path, "\n".join(script_lines(initial, stage)) + "\n")
        scripts[stage] = digest(path)
    record(
        HERE / "prepared.json",
        {
            "epoch_utc": EPOCH + "Z",
            "initial_position_gcrs_km": r,
            "initial_velocity_gcrs_km_s": v,
            "comparison_convention": "Phase A validated Astropy TEME→GCRS to GMAT EarthICRF",
            "config_sha256": digest(CONFIG),
            "eop_sha256": config.earth_orientation.table_sha256,
            "gravity_file": str(GRAVITY),
            "gravity_sha256": digest(GRAVITY),
            "gmat_executable_sha256": digest(GMAT_BIN / "GmatConsole.exe"),
            "startup_sha256": digest(GMAT_BIN / "gmat_startup_file.txt"),
            "pck_sha256": digest(PCK),
            "scripts_sha256": scripts,
            "limits": {
                "initial_position_km": INITIAL_POSITION_LIMIT_KM,
                "initial_velocity_km_s": INITIAL_VELOCITY_LIMIT_KM_S,
                "convergence_position_km": CONVERGENCE_POSITION_LIMIT_KM,
                "convergence_velocity_km_s": CONVERGENCE_VELOCITY_LIMIT_KM_S,
            },
        },
    )
    print("Phase B configuration and all GMAT scripts frozen")


def prepared(stage: str) -> dict:
    data = json.loads((HERE / "prepared.json").read_text())
    if digest(CONFIG) != data["config_sha256"] or digest(GRAVITY) != data["gravity_sha256"]:
        raise RuntimeError("Canonical config or GMAT gravity file changed")
    if digest(HERE / f"{stage}.script") != data["scripts_sha256"][stage]:
        raise RuntimeError(f"Frozen {stage} script changed")
    return data


def run_gmat(stage: str) -> None:
    prepared(stage)
    marker = HERE / f"{stage}_stdout.txt"
    if marker.exists():
        raise RuntimeError(f"{stage} was already executed; do not rerun")
    script = HERE / f"{stage}.script"
    completed = subprocess.run(
        [
            str(GMAT_BIN / "GmatConsole.exe"),
            "--logfile",
            str(HERE / f"{stage}_log.txt"),
            "--exit",
            "--run",
            str(script),
        ],
        cwd=GMAT_BIN,
        input="q\n",
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    write(marker, completed.stdout)
    write(HERE / f"{stage}_stderr.txt", completed.stderr)
    if completed.returncode != 0 or "Mission run completed." not in completed.stdout:
        raise RuntimeError(
            f"GMAT {stage} failed; inspect retained stdout/log (exit {completed.returncode})"
        )


def parse_states(path: Path, expected_count: int) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) == 10 and re.fullmatch(r"\d{1,2}", fields[0]):
            rows.append(
                {
                    "gmat_utc": " ".join(fields[:4]),
                    "position_km": [float(x) for x in fields[4:7]],
                    "velocity_km_s": [float(x) for x in fields[7:10]],
                }
            )
    if len(rows) != expected_count:
        raise RuntimeError(f"Expected {expected_count} state rows in {path}, found {len(rows)}")
    return rows


def check_gate() -> None:
    data = prepared("gate")
    run_gmat("gate")
    row = parse_states(HERE / "gate_report.txt", 1)[0]
    if row["gmat_utc"] != "27 Jun 2000 20:00:00.000":
        raise RuntimeError(f"Initial GMAT report has wrong epoch: {row['gmat_utc']}")
    dr = [a - b for a, b in zip(row["position_km"], data["initial_position_gcrs_km"], strict=True)]
    dv = [
        a - b for a, b in zip(row["velocity_km_s"], data["initial_velocity_gcrs_km_s"], strict=True)
    ]
    passed = norm(dr) <= INITIAL_POSITION_LIMIT_KM and norm(dv) <= INITIAL_VELOCITY_LIMIT_KM_S
    record(
        HERE / "gate.json",
        {
            "status": "PASS" if passed else "FAIL",
            "intended_position_km": data["initial_position_gcrs_km"],
            "intended_velocity_km_s": data["initial_velocity_gcrs_km_s"],
            "gmat": row,
            "gmat_minus_intended_position_km": dr,
            "gmat_minus_intended_velocity_km_s": dv,
            "position_residual_norm_km": norm(dr),
            "velocity_residual_norm_km_s": norm(dv),
            "report_sha256": digest(HERE / "gate_report.txt"),
        },
    )
    print(
        f"Initial-state gate: {'PASS' if passed else 'FAIL'}; |dr|={norm(dr):.12g} km; |dv|={norm(dv):.12g} km/s"
    )
    if not passed:
        raise RuntimeError("Initial-state compatibility gate failed; propagation prohibited")


def run_dynamics(stage: str) -> None:
    if json.loads((HERE / "gate.json").read_text())["status"] != "PASS":
        raise RuntimeError("Initial-state gate must pass before propagation")
    if stage == "refined" and not (HERE / "base_report.txt").exists():
        raise RuntimeError("Base trajectory must finish before refinement")
    run_gmat(stage)
    rows = parse_states(HERE / f"{stage}_report.txt", len(OFFSETS_MIN))
    for minute, row in zip(OFFSETS_MIN, rows, strict=True):
        expected = f"27 Jun 2000 20:{minute:02d}:00.000"
        if row["gmat_utc"] != expected or not all(
            math.isfinite(x) for x in row["position_km"] + row["velocity_km_s"]
        ):
            raise RuntimeError(f"{stage} epoch or finite-state defect at {minute} min")
    record(
        HERE / f"{stage}.json",
        {
            "status": "COMPLETED",
            "max_step_s": 30 if stage == "refined" else 60,
            "states": rows,
            "script_sha256": digest(HERE / f"{stage}.script"),
            "report_sha256": digest(HERE / f"{stage}_report.txt"),
        },
    )
    print(f"{stage}: 9 exact-epoch finite states")


def analyze() -> None:
    data = prepared("base")
    base = json.loads((HERE / "base.json").read_text())["states"]
    refined = json.loads((HERE / "refined.json").read_text())["states"]
    final_dr = [
        a - b for a, b in zip(base[-1]["position_km"], refined[-1]["position_km"], strict=True)
    ]
    final_dv = [
        a - b for a, b in zip(base[-1]["velocity_km_s"], refined[-1]["velocity_km_s"], strict=True)
    ]
    convergence_pass = (
        norm(final_dr) <= CONVERGENCE_POSITION_LIMIT_KM
        and norm(final_dv) <= CONVERGENCE_VELOCITY_LIMIT_KM_S
    )
    record(
        HERE / "convergence.json",
        {
            "status": "PASS" if convergence_pass else "FAIL",
            "base_final": base[-1],
            "refined_final": refined[-1],
            "base_minus_refined_position_km": final_dr,
            "base_minus_refined_velocity_km_s": final_dv,
            "position_difference_norm_km": norm(final_dr),
            "velocity_difference_norm_km_s": norm(final_dv),
        },
    )
    print(
        f"Convergence: {'PASS' if convergence_pass else 'FAIL'}; |dr|={norm(final_dr):.12g} km; |dv|={norm(final_dv):.12g} km/s"
    )
    if not convergence_pass:
        raise RuntimeError("Integrator refinement failed; cross-model interpretation prohibited")
    config = load_analysis_config(CONFIG)
    propagator = Sgp4Propagator(config.tle)
    rows = []
    with (
        iers.conf.set_temp("auto_download", False),
        iers.earth_orientation_table.set(config.earth_orientation.build_table()),
    ):
        for minute, gmat in zip(OFFSETS_MIN, base, strict=True):
            instant = Time(f"2000-06-27T20:{minute:02d}:00", format="isot", scale="utc")
            r, v = _astropy_gcrs(propagator, instant)
            dr = [a - b for a, b in zip(gmat["position_km"], r, strict=True)]
            dv = [a - b for a, b in zip(gmat["velocity_km_s"], v, strict=True)]
            rows.append(
                {
                    "utc": instant.isot + "Z",
                    "offset_min": minute,
                    "production_position_gcrs_km": r,
                    "gmat_position_earthicrf_km": gmat["position_km"],
                    "gmat_minus_production_position_km": dr,
                    "position_residual_norm_km": norm(dr),
                    "production_velocity_gcrs_km_s": v,
                    "gmat_velocity_earthicrf_km_s": gmat["velocity_km_s"],
                    "gmat_minus_production_velocity_km_s": dv,
                    "velocity_residual_norm_km_s": norm(dv),
                }
            )
    if not all(
        math.isfinite(x)
        for row in rows
        for x in (row["position_residual_norm_km"], row["velocity_residual_norm_km_s"])
    ):
        raise RuntimeError("Nonfinite cross-model residual")
    record(
        HERE / "state_comparison.json",
        {
            "status": "REVIEW_REQUIRED",
            "cross_model_magnitude_limit": None,
            "config_sha256": data["config_sha256"],
            "gravity_sha256": data["gravity_sha256"],
            "samples": rows,
        },
    )
    with (HERE / "state_comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            ["utc", "offset_min"]
            + [
                f"{name}_{axis}"
                for name in (
                    "production_r_km",
                    "gmat_r_km",
                    "gmat_minus_production_r_km",
                    "production_v_km_s",
                    "gmat_v_km_s",
                    "gmat_minus_production_v_km_s",
                )
                for axis in "xyz"
            ]
            + ["position_norm_km", "velocity_norm_km_s"]
        )
        for row in rows:
            writer.writerow(
                [
                    row["utc"],
                    row["offset_min"],
                    *row["production_position_gcrs_km"],
                    *row["gmat_position_earthicrf_km"],
                    *row["gmat_minus_production_position_km"],
                    *row["production_velocity_gcrs_km_s"],
                    *row["gmat_velocity_earthicrf_km_s"],
                    *row["gmat_minus_production_velocity_km_s"],
                    row["position_residual_norm_km"],
                    row["velocity_residual_norm_km_s"],
                ]
            )
    print("Cross-model state vectors saved for continuity review; no magnitude threshold")


def contacts() -> None:
    data = json.loads((HERE / "state_comparison.json").read_text())
    if data["status"] != "CONTINUOUS_REVIEWED":
        raise RuntimeError("State comparison needs continuity review before ContactLocator")
    run_gmat("contacts")
    observed = parse_contacts(HERE / "contacts_report.txt")
    production = json.loads(PRODUCTION_RESULT.read_text(encoding="utf-8"))
    by_name = {row["station_name"]: row["windows"] for row in production["station_access"]}
    names = {
        "Greenwich": "Equator Greenwich synthetic fixed WGS84 station",
        "OneNorthOneEast": "Synthetic 1N 1E WGS84 station",
    }
    record(
        HERE / "contacts.json",
        {
            "status": "DIAGNOSTIC",
            "cross_model_timing_limit": None,
            "production_run_sha256": digest(PRODUCTION_RESULT),
            "gmat_report_sha256": digest(HERE / "contacts_report.txt"),
            "stations": [
                {
                    "observer": key,
                    "production_windows": by_name[value],
                    "gmat_windows": observed[key],
                }
                for key, value in names.items()
            ],
        },
    )
    print("Phase B numerical-trajectory contact events saved")


def summarize_contacts() -> None:
    evidence = json.loads((HERE / "contacts.json").read_text(encoding="utf-8"))
    comparisons = []
    for station in evidence["stations"]:
        production = station["production_windows"]
        gmat = station["gmat_windows"]
        pairs = []
        for left, right in zip(production, gmat):
            pairs.append(
                {
                    "production": left,
                    "gmat": right,
                    "gmat_minus_production_aos_s": float(
                        (_time(right["start_utc"]) - _time(left["start_utc"])).to_value("sec")
                    ),
                    "gmat_minus_production_los_s": float(
                        (_time(right["end_utc"]) - _time(left["end_utc"])).to_value("sec")
                    ),
                    "gmat_minus_production_duration_s": right["duration_s"] - left["duration_s"],
                }
            )
        comparisons.append(
            {
                "observer": station["observer"],
                "production_event_count": len(production),
                "gmat_event_count": len(gmat),
                "paired_by_chronological_order": pairs,
            }
        )
    record(
        HERE / "contact_comparison.json",
        {
            "status": "DIAGNOSTIC",
            "cross_model_timing_limit": None,
            "source_report_sha256": evidence["gmat_report_sha256"],
            "stations": comparisons,
        },
    )
    print("Signed GMAT-minus-production event differences saved")


def main(stage: str) -> None:
    commands = {
        "prepare": prepare,
        "gate": check_gate,
        "base": lambda: run_dynamics("base"),
        "refined": lambda: run_dynamics("refined"),
        "analyze": analyze,
        "contacts": contacts,
        "summarize-contacts": summarize_contacts,
    }
    commands[stage]()


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in (
        "prepare",
        "gate",
        "base",
        "refined",
        "analyze",
        "contacts",
        "summarize-contacts",
    ):
        raise SystemExit("Usage: python -m validation.gmat.phase_b.run_diagnostic STAGE")
    main(sys.argv[1])
