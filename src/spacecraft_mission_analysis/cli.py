"""Thin command-line invocation of the versioned analysis and output contracts."""

import argparse
import shutil
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from .input import InputConfigError, load_analysis_config
from .output import csv_bundle, write_csv_bundle, write_json
from .run import AnalysisResult, RunStatus, run_analysis


def _write_outputs(result: AnalysisResult, output_dir: Path) -> None:
    """Stage a complete bundle, then publish each file without replacing evidence."""
    csv_names = tuple(csv_bundle(result))
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as exc:
        raise OSError(f"cannot create output directory {output_dir}: {exc}") from exc

    csv_dir = output_dir / "csv"
    if csv_dir.is_symlink() or (csv_dir.exists() and not csv_dir.is_dir()):
        raise OSError(f"output path is not a directory: {csv_dir}")
    targets = (output_dir / "run.json", *(csv_dir / name for name in csv_names))
    for target in targets:
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"output artifact already exists: {target}")

    csv_dir.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix=".analysis-", dir=output_dir) as temporary:
        staged = Path(temporary)
        write_json(result, staged / "run.json")
        write_csv_bundle(result, staged / "csv")
        sources = (staged / "run.json", *(staged / "csv" / name for name in csv_names))
        published: list[Path] = []
        try:
            for source, target in zip(sources, targets):
                with source.open("rb") as staged_file, target.open("xb") as final_file:
                    published.append(target)
                    shutil.copyfileobj(staged_file, final_file)
        except OSError:
            for target in reversed(published):
                target.unlink()
            raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one archived spacecraft analysis")
    parser.add_argument("config", metavar="CONFIG", help="versioned analysis JSON")
    parser.add_argument("--output-dir", required=True, metavar="PATH", help="new output location")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    try:
        config = load_analysis_config(args.config)
    except InputConfigError as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2

    result = run_analysis(config)
    output_dir = Path(args.output_dir)
    try:
        _write_outputs(result, output_dir)
    except OSError as exc:
        print(f"output error: {exc}", file=sys.stderr)
        return 4

    if result.status == RunStatus.FAILED:
        print(f"status=FAILED output={output_dir}", file=sys.stderr)
        for notice in result.notices:
            print(f"{notice.code}: {notice.message}", file=sys.stderr)
        return 3

    windows = sum(len(item.windows) for item in result.station_access or ())
    warnings = [notice for notice in result.notices if notice.severity == "WARNING"]
    print(
        f"status={result.status.value} output={output_dir} "
        f"stations={len(result.config.stations)} station_access_windows={windows} "
        f"merged_coverage_intervals={result.coverage.access_window_count} "
        f"coverage_fraction={result.coverage.coverage_fraction:.12f} "
        f"warnings={len(warnings)}"
    )
    for notice in warnings:
        print(f"{notice.code}: {notice.message}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
