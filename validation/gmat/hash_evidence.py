"""Write portable SHA-256 manifests for retained GMAT diagnostic evidence."""

import json
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    for name in ("fixed_gate_diagnostic", "icrf", "phase_a"):
        folder = ROOT / name
        files = {
            path.relative_to(folder).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in sorted(folder.rglob("*"))
            if path.is_file()
            and path.name != "sha256_manifest.json"
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
        }
        destination = folder / "sha256_manifest.json"
        destination.write_text(json.dumps(files, indent=2) + "\n", encoding="utf-8")
        print(f"{name}: {len(files)} files, {destination}")


if __name__ == "__main__":
    main()
