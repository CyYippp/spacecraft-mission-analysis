"""Hash installed GMAT orientation, shape, ephemeris and time inputs read-only."""

import json
from hashlib import sha256
from pathlib import Path

GMAT = Path(r"C:\Users\Cyrus\Applications\GMAT\R2026a")
HERE = Path(__file__).resolve().parent
FILES = {
    "startup": "bin/gmat_startup_file.txt",
    "eop": "data/planetary_coeff/eopc04_08.62-now",
    "planetary_pck": "data/planetary_coeff/SPICEPlanetaryConstantsKernel.tpc",
    "earth_predicted_bpc": "data/planetary_coeff/SPICEEarthPredictedKernel.bpc",
    "earth_current_bpc": "data/planetary_coeff/SPICEEarthCurrentKernel.bpc",
    "earth_latest_bpc": "data/planetary_coeff/earth_latest_high_prec.bpc",
    "planetary_spk": "data/planetary_ephem/spk/DE405AllPlanets.bsp",
    "spice_lsk": "data/time/SPICELeapSecondKernel.tls",
    "core_leap_seconds": "data/time/tai-utc.dat",
}


def main() -> None:
    files = {}
    for label, relative_path in FILES.items():
        path = GMAT / relative_path
        files[label] = {
            "relative_to_gmat_installation": relative_path,
            "sha256": sha256(path.read_bytes()).hexdigest(),
        }
    result = {
        "gmat_release": "R2026a",
        "installation_root_at_execution": str(GMAT),
        "source": "Installed files and kernel-load names in Phase A raw GMAT stdout",
        "production_eop_mode": "explicit synthetic zero UT1-UTC/xp/yp",
        "gmat_core_eop_source": FILES["eop"],
        "contact_spice_orientation_sources": [
            FILES["earth_predicted_bpc"],
            FILES["earth_current_bpc"],
            FILES["earth_latest_bpc"],
        ],
        "contact_spice_shape_source": FILES["planetary_pck"],
        "files": files,
    }
    destination = HERE / "environment_manifest.json"
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
