"""Measure the fixed-STK import discrepancy without changing production code."""

import json
from hashlib import sha256
from math import atan2, cos, hypot, sin, sqrt
from pathlib import Path

EVIDENCE = Path(__file__).resolve().parent / "fixed_gate_diagnostic"
EARTH_ROTATION_RAD_S = 7.2921150e-5


def reported_position(path: Path) -> tuple[str, list[float]]:
    fields = path.read_text(encoding="utf-8").splitlines()[-1].split()
    return " ".join(fields[:4]), [float(value) for value in fields[-3:]]


def norm(values: list[float]) -> float:
    return sqrt(sum(value * value for value in values))


def main() -> None:
    production = json.loads((EVIDENCE / "production_expected.json").read_text(encoding="utf-8"))
    position = production["60"]["position_km"]
    results = {}
    for name, report in (
        ("original", EVIDENCE / "fixed_import_report.txt"),
        ("minus_one_second", EVIDENCE / "shift_minus1" / "shifted_report.txt"),
        ("plus_one_second", EVIDENCE / "shift_plus1" / "shifted_report.txt"),
    ):
        time, actual = reported_position(report)
        residual = [gmat - reference for gmat, reference in zip(actual, position)]
        results[name] = {
            "reported_utc": time,
            "position_km": actual,
            "gmat_minus_production_km": residual,
            "residual_norm_km": norm(residual),
        }

    actual = results["original"]["position_km"]
    angle = atan2(
        position[0] * actual[1] - position[1] * actual[0],
        position[0] * actual[0] + position[1] * actual[1],
    )
    rotated = [
        cos(angle) * position[0] - sin(angle) * position[1],
        sin(angle) * position[0] + cos(angle) * position[1],
        position[2],
    ]
    post_fit = [gmat - fitted for gmat, fitted in zip(actual, rotated)]
    one_second_rotated = [
        cos(EARTH_ROTATION_RAD_S) * position[0] - sin(EARTH_ROTATION_RAD_S) * position[1],
        sin(EARTH_ROTATION_RAD_S) * position[0] + cos(EARTH_ROTATION_RAD_S) * position[1],
        position[2],
    ]
    post_one_second = [gmat - fitted for gmat, fitted in zip(actual, one_second_rotated)]
    direct_fields = (
        (EVIDENCE / "direct_fixed_report.txt").read_text(encoding="utf-8").splitlines()[-1].split()
    )
    import_fields = (
        (EVIDENCE / "epoch_trace_report.txt").read_text(encoding="utf-8").splitlines()[-1].split()
    )
    direct_fixed_and_inertial = [float(value) for value in direct_fields[-6:]]
    imported_fixed_and_inertial = [float(value) for value in import_fields[-6:]]
    inertial_delta = [
        imported - direct
        for imported, direct in zip(imported_fixed_and_inertial[3:], direct_fixed_and_inertial[3:])
    ]
    original_file = EVIDENCE / "production_fixed_1s_gate.e"
    output = {
        "rotation": {
            "xy_radius_km": hypot(position[0], position[1]),
            "xy_residual_km": hypot(actual[0] - position[0], actual[1] - position[1]),
            "best_fit_z_angle_rad": angle,
            "equivalent_sidereal_seconds": angle / EARTH_ROTATION_RAD_S,
            "one_sidereal_second_delta_km": [
                shifted - reference for shifted, reference in zip(one_second_rotated, position)
            ],
            "post_one_sidereal_second_residual_km": post_one_second,
            "post_fit_residual_km": post_fit,
            "post_fit_residual_norm_km": norm(post_fit),
            "z_residual_km": actual[2] - position[2],
        },
        "label_shift_tests": results,
        "direct_gmat_earth_fixed_control": {
            "direct_fixed_position_km": direct_fixed_and_inertial[:3],
            "direct_earth_mj2000_eq_position_km": direct_fixed_and_inertial[3:],
            "imported_earth_mj2000_eq_position_km": imported_fixed_and_inertial[3:],
            "imported_minus_direct_inertial_km": inertial_delta,
            "inertial_residual_norm_km": norm(inertial_delta),
        },
        "original_stk_sha256": sha256(original_file.read_bytes()).hexdigest(),
    }
    destination = EVIDENCE / "diagnosis.json"
    destination.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
