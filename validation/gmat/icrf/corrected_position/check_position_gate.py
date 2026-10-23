"""Frozen continuous-time GMAT ICRF position fidelity and convergence gates."""

import json
import re
import subprocess
import sys
from hashlib import sha256
from math import sqrt
from pathlib import Path

from astropy.time import Time
from astropy.utils import iers

from spacecraft_mission_analysis.input import load_analysis_config
from spacecraft_mission_analysis.orbit import Sgp4Propagator
from validation.gmat.icrf.check_transfer import CONFIG, _astropy_gcrs

HERE = Path(__file__).resolve().parent
ICRF_DIR = HERE.parent
GMAT_BIN = Path(r"C:\Users\Cyrus\Applications\GMAT\R2026a\bin")
ONE_SECOND_POSITION_LIMIT_KM = 0.001
CONVERGENCE_POSITION_LIMIT_KM = 0.0001
EPOCHS = (
    ("20:00:00.000", 60_000),
    ("20:00:00.500", 60_500),
    ("20:03:17.123", 257_123),
    ("20:10:00.000", 660_000),
    ("20:10:00.500", 660_500),
    ("20:17:43.371", 1_123_371),
    ("20:20:00.000", 1_260_000),
    ("20:20:00.500", 1_260_500),
    ("20:30:00.000", 1_860_000),
    ("20:30:00.500", 1_860_500),
    ("20:33:08.777", 2_048_777),
    ("20:39:59.500", 2_459_500),
    ("20:40:00.000", 2_460_000),
)


def _norm(values: list[float]) -> float:
    return sqrt(sum(value * value for value in values))


def _file_for_mode(mode: str) -> tuple[Path, str]:
    if mode == "1s":
        manifest = json.loads((ICRF_DIR / "ephemeris_manifest.json").read_text(encoding="utf-8"))
        ephemeris = ICRF_DIR / manifest["file"]
    elif mode == "0p5s":
        manifest = json.loads((HERE / "half_second_manifest.json").read_text(encoding="utf-8"))
        ephemeris = HERE / manifest["file"]
        one_second = json.loads((HERE / "position_gate_1s.json").read_text(encoding="utf-8"))
        if one_second["status"] != "PASS":
            raise RuntimeError("1 s production-reference position gate has not passed")
        if one_second["ephemeris_sha256"] != manifest["one_second_sha256"]:
            raise RuntimeError("1 s reference gate and 0.5 s file use different source files")
    else:
        raise ValueError("mode must be 1s or 0p5s")
    if sha256(ephemeris.read_bytes()).hexdigest() != manifest["sha256"]:
        raise RuntimeError(f"{mode} ephemeris changed after generation")
    return ephemeris, manifest["sha256"]


def _write_gmat_script(mode: str, ephemeris: Path, script: Path, report: Path) -> None:
    commands = [
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
        "Create Array initialState[6,1] finalState[6,1];",
        "Create String initialEpoch finalEpoch;",
        "Create ReportFile PositionReport;",
        f"PositionReport.Filename = '{report.as_posix()}';",
        "BeginMissionSequence;",
        "[initialEpoch, initialState, finalEpoch, finalState] = "
        "GetEphemStates('STK', ImportedVanguard, 'UTCGregorian', EarthICRF);",
        "ImportedVanguard.UTCGregorian = initialEpoch;",
    ]
    previous_ms = 0
    for _time_label, elapsed_ms in EPOCHS:
        step_ms = elapsed_ms - previous_ms
        if step_ms <= 0:
            raise RuntimeError("Diagnostic epochs are not strictly increasing")
        commands.append(
            "Propagate ImportedSTK(ImportedVanguard) "
            f"{{ImportedVanguard.ElapsedSecs = {step_ms / 1000:.3f}}};"
        )
        commands.append(
            "Report PositionReport ImportedVanguard.UTCGregorian "
            "ImportedVanguard.EarthICRF.X ImportedVanguard.EarthICRF.Y "
            "ImportedVanguard.EarthICRF.Z ImportedVanguard.EarthICRF.VX "
            "ImportedVanguard.EarthICRF.VY ImportedVanguard.EarthICRF.VZ;"
        )
        previous_ms = elapsed_ms
    script.write_text("\n".join(commands) + "\n", encoding="utf-8", newline="\n")


def _parse_report(report: Path) -> list[tuple[str, list[float]]]:
    rows = []
    for line in report.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) == 10 and re.fullmatch(r"\d{1,2}", fields[0]):
            rows.append((" ".join(fields[:4]), [float(value) for value in fields[4:]]))
    if len(rows) != len(EPOCHS):
        raise RuntimeError(f"Expected {len(EPOCHS)} GMAT rows, found {len(rows)}")
    return rows


def _direct_states() -> list[tuple[list[float], list[float]]]:
    config = load_analysis_config(CONFIG)
    conversion = json.loads((ICRF_DIR / "transfer_check.json").read_text(encoding="utf-8"))
    if conversion["status"] != "PASS":
        raise RuntimeError("Independent conversion gate has not passed")
    if sha256(CONFIG.read_bytes()).hexdigest() != conversion["config_sha256"]:
        raise RuntimeError("Canonical config changed after independent conversion check")
    if config.earth_orientation.table_sha256 != conversion["eop_table_sha256"]:
        raise RuntimeError("Canonical EOP table changed after independent conversion check")
    propagator = Sgp4Propagator(config.tle)
    states = []
    with (
        iers.conf.set_temp("auto_download", False),
        iers.earth_orientation_table.set(config.earth_orientation.build_table()),
    ):
        for time_label, _offset_ms in EPOCHS:
            time = Time(f"2000-06-27T{time_label}", format="isot", scale="utc")
            states.append(_astropy_gcrs(propagator, time))
    return states


def main(mode: str) -> int:
    ephemeris, ephemeris_sha256 = _file_for_mode(mode)
    script = HERE / f"position_gate_{mode}.script"
    report = HERE / f"position_gate_{mode}_report.txt"
    stdout = HERE / f"position_gate_{mode}_stdout.txt"
    stderr = HERE / f"position_gate_{mode}_stderr.txt"
    log = HERE / f"position_gate_{mode}_log.txt"
    result = HERE / f"position_gate_{mode}.json"
    _write_gmat_script(mode, ephemeris, script, report)
    completed = subprocess.run(
        [str(GMAT_BIN / "GmatConsole.exe"), "--logfile", str(log), "--exit", "--run", str(script)],
        cwd=GMAT_BIN,
        input="q\n",
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    stdout.write_text(completed.stdout, encoding="utf-8")
    stderr.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0 or "Mission run completed." not in completed.stdout:
        failure = {
            "status": "GMAT_EXECUTION_FAILED",
            "mode": mode,
            "ephemeris_sha256": ephemeris_sha256,
            "script_sha256": sha256(script.read_bytes()).hexdigest(),
            "gmat_returncode": completed.returncode,
        }
        result.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        print(f"GMAT execution failed for {mode}; see {stdout} and {log}")
        return 2
    reported = _parse_report(report)
    direct = _direct_states()
    one_second = None
    if mode == "0p5s":
        one_second = json.loads((HERE / "position_gate_1s.json").read_text(encoding="utf-8"))
    samples = []
    for index, ((time_label, _offset_ms), (epoch, gmat), reference) in enumerate(
        zip(EPOCHS, reported, direct, strict=True)
    ):
        expected_epoch = f"27 Jun 2000 {time_label}"
        direct_position, direct_velocity = reference
        position_delta = [
            value - expected for value, expected in zip(gmat[:3], direct_position, strict=True)
        ]
        velocity_delta = [
            value - expected for value, expected in zip(gmat[3:], direct_velocity, strict=True)
        ]
        sample = {
            "utc": f"2000-06-27T{time_label}Z",
            "gmat_reported_utc": epoch,
            "utc_label_matches": epoch == expected_epoch,
            "production_direct_gcrs_position_km": direct_position,
            "production_direct_gcrs_velocity_km_s": direct_velocity,
            "gmat_stk_earth_icrf_position_km": gmat[:3],
            "gmat_stk_earth_icrf_velocity_km_s": gmat[3:],
            "gmat_minus_production_position_km": position_delta,
            "position_residual_norm_km": _norm(position_delta),
            "gmat_minus_production_velocity_diagnostic_km_s": velocity_delta,
            "velocity_residual_diagnostic_norm_km_s": _norm(velocity_delta),
        }
        if one_second is not None:
            one_second_position = one_second["samples"][index]["gmat_stk_earth_icrf_position_km"]
            convergence_delta = [
                value - expected
                for value, expected in zip(one_second_position, gmat[:3], strict=True)
            ]
            sample["one_second_minus_half_second_position_km"] = convergence_delta
            sample["convergence_position_norm_km"] = _norm(convergence_delta)
        samples.append(sample)
    label_pass = all(row["utc_label_matches"] for row in samples)
    if mode == "1s":
        limit = ONE_SECOND_POSITION_LIMIT_KM
        maximum = max(row["position_residual_norm_km"] for row in samples)
    else:
        limit = CONVERGENCE_POSITION_LIMIT_KM
        maximum = max(row["convergence_position_norm_km"] for row in samples)
    output = {
        "status": "PASS" if label_pass and maximum <= limit else "FAIL",
        "mode": mode,
        "criterion": "direct_position_fidelity" if mode == "1s" else "position_convergence",
        "position_limit_km": limit,
        "maximum_position_residual_km": maximum,
        "velocity_role": "diagnostic_only_no_pass_fail_criterion",
        "ephemeris_sha256": ephemeris_sha256,
        "script_sha256": sha256(script.read_bytes()).hexdigest(),
        "raw_report_sha256": sha256(report.read_bytes()).hexdigest(),
        "gmat_returncode": completed.returncode,
        "samples": samples,
    }
    result.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"{mode} {output['status']} max position={maximum:.12g} km, limit={limit:.12g} km")
    for row in samples:
        residual = (
            row["position_residual_norm_km"]
            if mode == "1s"
            else row["convergence_position_norm_km"]
        )
        print(f"{row['utc']} position={residual:.12g} km label={row['utc_label_matches']}")
    return 0 if output["status"] == "PASS" else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m validation.gmat.icrf.corrected_position.check_position_gate 1s|0p5s"
        )
    raise SystemExit(main(sys.argv[1]))
