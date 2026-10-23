"""Export the frozen GMAT position-gate vectors to a reviewable CSV table."""

import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DESTINATION = HERE / "position_vectors.csv"


def main() -> None:
    first = json.loads((HERE / "position_gate_1s.json").read_text(encoding="utf-8"))
    second = json.loads((HERE / "position_gate_0p5s.json").read_text(encoding="utf-8"))
    if first["status"] != "PASS" or second["status"] != "PASS":
        raise RuntimeError("Both position gate results must be present and passed")
    columns = ["utc"]
    for prefix in ("production_gcrs", "gmat_1s_icrf", "gmat_0p5s_icrf"):
        columns.extend(f"{prefix}_{axis}_km" for axis in "xyz")
    columns.extend(("gmat_1s_minus_production_norm_km", "gmat_1s_minus_0p5s_norm_km"))
    with DESTINATION.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        for left, right in zip(first["samples"], second["samples"], strict=True):
            if left["utc"] != right["utc"]:
                raise RuntimeError("Position gate epoch lists differ")
            writer.writerow(
                [
                    left["utc"],
                    *left["production_direct_gcrs_position_km"],
                    *left["gmat_stk_earth_icrf_position_km"],
                    *right["gmat_stk_earth_icrf_position_km"],
                    left["position_residual_norm_km"],
                    right["convergence_position_norm_km"],
                ]
            )
    print(DESTINATION)


if __name__ == "__main__":
    main()
