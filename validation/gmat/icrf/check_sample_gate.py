"""Run the frozen GMAT STK ICRF exact-grid sample gate, retaining evidence."""

import json
import re
import subprocess
from hashlib import sha256
from math import sqrt
from pathlib import Path

from check_parser_gate import EPHEMERIS, GMAT_BIN, POSITION_LIMIT_KM, VELOCITY_LIMIT_KM_S

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "icrf_sample_gate.script"
REPORT = HERE / "icrf_sample_report.txt"
STDOUT = HERE / "icrf_sample_stdout.txt"
STDERR = HERE / "icrf_sample_stderr.txt"
LOG = HERE / "icrf_sample_log.txt"
RESULT = HERE / "icrf_sample_gate.json"
SAMPLES = (
    (60, "27 Jun 2000 20:00:00.000"),
    (1260, "27 Jun 2000 20:20:00.000"),
    (2460, "27 Jun 2000 20:40:00.000"),
)


def _norm(values: list[float]) -> float:
    return sqrt(sum(value * value for value in values))


def _expected_rows() -> dict[int, list[float]]:
    rows = {}
    for line in EPHEMERIS.read_text(encoding="ascii").splitlines():
        if re.match(r"^\d+\.\d+\s", line):
            values = [float(value) for value in line.split()]
            offset = int(values[0])
            if offset in (60, 1260, 2460):
                rows[offset] = values[1:]
    if len(rows) != len(SAMPLES):
        raise RuntimeError("Required exact ephemeris rows are absent")
    return rows


def _reported_rows() -> list[tuple[str, list[float]]]:
    rows = []
    for line in REPORT.read_text(encoding="utf-8").splitlines()[1:]:
        fields = line.split()
        if len(fields) == 10 and fields[0].isdigit():
            rows.append((" ".join(fields[:4]), [float(value) for value in fields[4:]]))
    if len(rows) != len(SAMPLES):
        raise RuntimeError(f"Expected 3 GMAT sample rows, found {len(rows)}")
    return rows


def main() -> int:
    parser_gate = json.loads((HERE / "icrf_parser_gate.json").read_text(encoding="utf-8"))
    if parser_gate["status"] != "PASS":
        raise RuntimeError("GMAT parser gate has not passed")
    manifest = json.loads((HERE / "ephemeris_manifest.json").read_text(encoding="utf-8"))
    if sha256(EPHEMERIS.read_bytes()).hexdigest() != manifest["sha256"]:
        raise RuntimeError("ICRF ephemeris changed after parser gate")
    if parser_gate["ephemeris_sha256"] != manifest["sha256"]:
        raise RuntimeError("Parser gate used a different ephemeris")
    script = f"""Create Spacecraft ImportedVanguard;
ImportedVanguard.DateFormat = UTCGregorian;
ImportedVanguard.Epoch = '27 Jun 2000 19:59:00.000';
ImportedVanguard.EphemerisName = '{EPHEMERIS.as_posix()}';
Create Propagator ImportedSTK;
ImportedSTK.Type = STK;
ImportedSTK.StepSize = 1;
ImportedSTK.CentralBody = Earth;
ImportedSTK.EpochFormat = A1ModJulian;
ImportedSTK.StartEpoch = 'FromSpacecraft';
Create Array initialState[6,1] finalState[6,1];
Create String initialEpoch finalEpoch;
Create ReportFile SampleReport;
SampleReport.Filename = '{REPORT.as_posix()}';
BeginMissionSequence;
[initialEpoch, initialState, finalEpoch, finalState] = GetEphemStates('STK', ImportedVanguard, 'UTCGregorian', EarthICRF);
ImportedVanguard.UTCGregorian = initialEpoch;
Propagate ImportedSTK(ImportedVanguard) {{ImportedVanguard.ElapsedSecs = 60}};
Report SampleReport ImportedVanguard.UTCGregorian ImportedVanguard.EarthICRF.X ImportedVanguard.EarthICRF.Y ImportedVanguard.EarthICRF.Z ImportedVanguard.EarthICRF.VX ImportedVanguard.EarthICRF.VY ImportedVanguard.EarthICRF.VZ;
Propagate ImportedSTK(ImportedVanguard) {{ImportedVanguard.ElapsedSecs = 1200}};
Report SampleReport ImportedVanguard.UTCGregorian ImportedVanguard.EarthICRF.X ImportedVanguard.EarthICRF.Y ImportedVanguard.EarthICRF.Z ImportedVanguard.EarthICRF.VX ImportedVanguard.EarthICRF.VY ImportedVanguard.EarthICRF.VZ;
Propagate ImportedSTK(ImportedVanguard) {{ImportedVanguard.ElapsedSecs = 1200}};
Report SampleReport ImportedVanguard.UTCGregorian ImportedVanguard.EarthICRF.X ImportedVanguard.EarthICRF.Y ImportedVanguard.EarthICRF.Z ImportedVanguard.EarthICRF.VX ImportedVanguard.EarthICRF.VY ImportedVanguard.EarthICRF.VZ;
"""
    SCRIPT.write_text(script, encoding="utf-8", newline="\n")
    completed = subprocess.run(
        [str(GMAT_BIN / "GmatConsole.exe"), "--logfile", str(LOG), "--exit", "--run", str(SCRIPT)],
        cwd=GMAT_BIN,
        input="q\n",
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    STDOUT.write_text(completed.stdout, encoding="utf-8")
    STDERR.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0 or "Mission run completed." not in completed.stdout:
        print(f"GMAT failed before sample gate; return code {completed.returncode}")
        return 2
    expected = _expected_rows()
    actual = _reported_rows()
    results = []
    for (offset, expected_epoch), (epoch, state) in zip(SAMPLES, actual, strict=True):
        delta = [
            value - reference for value, reference in zip(state, expected[offset], strict=True)
        ]
        position_norm = _norm(delta[:3])
        velocity_norm = _norm(delta[3:])
        results.append(
            {
                "offset_s": offset,
                "reported_utc": epoch,
                "expected_utc": expected_epoch,
                "gmat_earth_icrf": state,
                "serialized_stk_icrf": expected[offset],
                "gmat_minus_file": delta,
                "position_residual_norm_km": position_norm,
                "velocity_residual_norm_km_s": velocity_norm,
                "pass": epoch == expected_epoch
                and position_norm <= POSITION_LIMIT_KM
                and velocity_norm <= VELOCITY_LIMIT_KM_S,
            }
        )
    report = {
        "status": "PASS" if all(row["pass"] for row in results) else "FAIL",
        "position_limit_km": POSITION_LIMIT_KM,
        "velocity_limit_km_s": VELOCITY_LIMIT_KM_S,
        "ephemeris_sha256": manifest["sha256"],
        "script_sha256": sha256(SCRIPT.read_bytes()).hexdigest(),
        "raw_report_sha256": sha256(REPORT.read_bytes()).hexdigest(),
        "samples": results,
    }
    RESULT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: {RESULT}")
    for row in results:
        print(
            f"{row['reported_utc']} position={row['position_residual_norm_km']:.12g} km "
            f"velocity={row['velocity_residual_norm_km_s']:.12g} km/s "
            f"{'PASS' if row['pass'] else 'FAIL'}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
