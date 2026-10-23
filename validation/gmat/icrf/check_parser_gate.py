"""Run the frozen GMAT ICRF endpoint parser gate, retaining raw evidence."""

import json
import re
import subprocess
from hashlib import sha256
from math import sqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
GMAT_BIN = Path(r"C:\Users\Cyrus\Applications\GMAT\R2026a\bin")
EPHEMERIS = HERE / "vanguard_icrf_1s.e"
SCRIPT = HERE / "icrf_parser_gate.script"
REPORT = HERE / "icrf_parser_report.txt"
STDOUT = HERE / "icrf_parser_stdout.txt"
STDERR = HERE / "icrf_parser_stderr.txt"
LOG = HERE / "icrf_parser_log.txt"
RESULT = HERE / "icrf_parser_gate.json"
POSITION_LIMIT_KM = 1e-6
VELOCITY_LIMIT_KM_S = 1e-9


def _norm(values: list[float]) -> float:
    return sqrt(sum(value * value for value in values))


def _ephemeris_endpoints() -> tuple[list[float], list[float]]:
    lines = EPHEMERIS.read_text(encoding="ascii").splitlines()
    rows = [line for line in lines if re.match(r"^\d+\.\d+\s", line)]
    if len(rows) != 2521:
        raise RuntimeError(f"Expected 2521 ephemeris rows, found {len(rows)}")
    first, last = (
        [float(value) for value in rows[0].split()],
        [float(value) for value in rows[-1].split()],
    )
    if first[0] != 0 or last[0] != 2520:
        raise RuntimeError("Ephemeris endpoint offsets are not the frozen grid")
    return first[1:], last[1:]


def _report_states() -> tuple[str, list[float], str, list[float]]:
    lines = REPORT.read_text(encoding="utf-8").splitlines()
    if len(lines) < 7:
        raise RuntimeError("GMAT endpoint report is incomplete")
    columns = re.split(r"\s{2,}", lines[1].strip())
    if len(columns) != 4:
        raise RuntimeError(f"Unexpected GMAT endpoint report columns: {columns!r}")
    first_epoch, first_value, last_epoch, last_value = columns
    first = [float(first_value)]
    last = [float(last_value)]
    for line in lines[2:7]:
        pair = re.split(r"\s{2,}", line.strip())
        if len(pair) != 2:
            raise RuntimeError(f"Unexpected GMAT endpoint state row: {line!r}")
        first.append(float(pair[0]))
        last.append(float(pair[1]))
    return first_epoch, first, last_epoch, last


def main() -> int:
    manifest = json.loads((HERE / "ephemeris_manifest.json").read_text(encoding="utf-8"))
    if sha256(EPHEMERIS.read_bytes()).hexdigest() != manifest["sha256"]:
        raise RuntimeError("ICRF ephemeris does not match its generation manifest")
    expected_first, expected_last = _ephemeris_endpoints()
    script = f"""Create Spacecraft ImportedVanguard;
ImportedVanguard.DateFormat = UTCGregorian;
ImportedVanguard.Epoch = '27 Jun 2000 19:59:00.000';
ImportedVanguard.EphemerisName = '{EPHEMERIS.as_posix()}';
Create Array initialState[6,1] finalState[6,1];
Create String initialEpoch finalEpoch;
Create ReportFile GateReport;
GateReport.Filename = '{REPORT.as_posix()}';
BeginMissionSequence;
[initialEpoch, initialState, finalEpoch, finalState] = GetEphemStates('STK', ImportedVanguard, 'UTCGregorian', EarthICRF);
Report GateReport initialEpoch initialState finalEpoch finalState;
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
        print(f"GMAT failed before parser gate; return code {completed.returncode}")
        return 2
    first_epoch, actual_first, last_epoch, actual_last = _report_states()
    results = []
    for label, epoch, actual, expected, expected_epoch in (
        ("first", first_epoch, actual_first, expected_first, "27 Jun 2000 19:59:00.000"),
        ("last", last_epoch, actual_last, expected_last, "27 Jun 2000 20:41:00.000"),
    ):
        delta = [a - b for a, b in zip(actual, expected, strict=True)]
        position_norm = _norm(delta[:3])
        velocity_norm = _norm(delta[3:])
        results.append(
            {
                "endpoint": label,
                "reported_utc": epoch,
                "expected_utc": expected_epoch,
                "gmat_earth_icrf": actual,
                "serialized_stk_icrf": expected,
                "gmat_minus_file": delta,
                "position_residual_norm_km": position_norm,
                "velocity_residual_norm_km_s": velocity_norm,
                "pass": epoch == expected_epoch
                and position_norm <= POSITION_LIMIT_KM
                and velocity_norm <= VELOCITY_LIMIT_KM_S,
            }
        )
    report = {
        "status": "PASS" if all(item["pass"] for item in results) else "FAIL",
        "position_limit_km": POSITION_LIMIT_KM,
        "velocity_limit_km_s": VELOCITY_LIMIT_KM_S,
        "ephemeris_sha256": manifest["sha256"],
        "script_sha256": sha256(SCRIPT.read_bytes()).hexdigest(),
        "raw_report_sha256": sha256(REPORT.read_bytes()).hexdigest(),
        "gmat_returncode": completed.returncode,
        "endpoints": results,
    }
    RESULT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['status']}: {RESULT}")
    for result in results:
        print(
            f"{result['endpoint']} {result['reported_utc']} "
            f"position={result['position_residual_norm_km']:.12g} km "
            f"velocity={result['velocity_residual_norm_km_s']:.12g} km/s "
            f"{'PASS' if result['pass'] else 'FAIL'}"
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
