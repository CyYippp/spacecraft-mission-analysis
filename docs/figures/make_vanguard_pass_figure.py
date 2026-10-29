"""Draw the archived Vanguard 1 elevation curves as light and dark README SVGs.

Run from the repository root after `python -m pip install .`:

    python docs/figures/make_vanguard_pass_figure.py

Curves are sampled from the production elevation chain; event times and peaks
are read from the committed `examples/vanguard_run/run.json`, not recomputed.
"""

import json
from pathlib import Path

import astropy.units as u
from astropy.time import Time
from astropy.utils import iers

from spacecraft_mission_analysis.elevation import satellite_elevation_deg
from spacecraft_mission_analysis.input import load_analysis_config
from spacecraft_mission_analysis.orbit import Sgp4Propagator

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "examples" / "vanguard_run"
OUT = Path(__file__).resolve().parent
SAMPLE_STEP_S = 10.0

WIDTH, HEIGHT = 860, 420
LEFT, RIGHT, TOP, BOTTOM = 64, 24, 92, 56
Y_MIN, Y_MAX = -15.0, 25.0

THEMES = {
    "light": {
        "surface": "#fcfcfb",
        "ink": "#0b0b0b",
        "secondary": "#52514e",
        "muted": "#898781",
        "grid": "#e1e0d9",
        "axis": "#c3c2b7",
        "series": ("#2a78d6", "#eb6834"),
    },
    "dark": {
        "surface": "#1a1a19",
        "ink": "#f0efec",
        "secondary": "#c3c2b7",
        "muted": "#898781",
        "grid": "#2c2c2a",
        "axis": "#383835",
        "series": ("#3987e5", "#d95926"),
    },
}
LABELS = ("Greenwich, 0°N 0°E", "1°N 1°E")


def sample_curves(config_path: Path) -> tuple[list[float], list[list[float]]]:
    config = load_analysis_config(config_path)
    steps = round((config.end - config.start).to_value(u.s) / SAMPLE_STEP_S)
    offsets = [k * SAMPLE_STEP_S for k in range(steps + 1)]
    with (
        iers.conf.set_temp("auto_download", False),
        iers.earth_orientation_table.set(config.earth_orientation.build_table()),
    ):
        propagator = Sgp4Propagator(config.tle)
        curves = [
            [
                satellite_elevation_deg(propagator, station, config.start + offset * u.s)
                for offset in offsets
            ]
            for station in config.stations
        ]
    return offsets, curves


def draw(theme: dict, offsets: list[float], curves: list[list[float]], run: dict) -> str:
    start = Time(run["configuration"]["analysis_start_utc"].replace("Z", ""), scale="utc")
    span_s = offsets[-1]
    plot_w, plot_h = WIDTH - LEFT - RIGHT, HEIGHT - TOP - BOTTOM

    def x(seconds: float) -> float:
        return LEFT + seconds / span_s * plot_w

    def y(elevation: float) -> float:
        return TOP + (Y_MAX - elevation) / (Y_MAX - Y_MIN) * plot_h

    def seconds_since_start(stamp: str) -> float:
        return (Time(stamp.replace("Z", ""), scale="utc") - start).to_value(u.s)

    font = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" font-family="{font}" role="img" '
        'aria-label="Elevation of Vanguard 1 above two ground stations, 27 June 2000, '
        '20:00 to 20:40 UTC, with the 10 degree visibility mask">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" rx="8" fill="{theme["surface"]}"/>',
        f'<text x="{LEFT}" y="34" font-size="18" font-weight="600" fill="{theme["ink"]}">'
        "Vanguard 1 passing over two ground stations, 27 June 2000</text>",
        f'<text x="{LEFT}" y="58" font-size="13" fill="{theme["secondary"]}">'
        "The tool finds where each curve crosses the 10° mask. NASA's GMAT found the same "
        "crossings to within 0.05 s.</text>",
    ]
    for elevation in range(int(Y_MIN), int(Y_MAX) + 1, 5):
        stroke = theme["axis"] if elevation == 0 else theme["grid"]
        parts.append(
            f'<line x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y(elevation):.1f}" '
            f'y2="{y(elevation):.1f}" stroke="{stroke}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{LEFT - 10}" y="{y(elevation) + 4:.1f}" font-size="12" '
            f'text-anchor="end" fill="{theme["muted"]}">{elevation}°</text>'
        )
    for minute in range(0, round(span_s / 60) + 1, 5):
        parts.append(
            f'<text x="{x(minute * 60):.1f}" y="{HEIGHT - BOTTOM + 22}" font-size="12" '
            f'text-anchor="middle" fill="{theme["muted"]}">20:{minute:02d}</text>'
        )
    parts.append(
        f'<text x="{WIDTH - RIGHT}" y="{HEIGHT - 12}" font-size="12" text-anchor="end" '
        f'fill="{theme["muted"]}">UTC</text>'
    )
    parts.append(
        f'<text x="18" y="{TOP + plot_h / 2:.1f}" font-size="12" fill="{theme["muted"]}" '
        f'text-anchor="middle" transform="rotate(-90 18 {TOP + plot_h / 2:.1f})">'
        "Elevation above horizon</text>"
    )
    mask = run["configuration"]["minimum_elevation_deg"]
    parts.append(
        f'<line x1="{LEFT}" x2="{WIDTH - RIGHT}" y1="{y(mask):.1f}" y2="{y(mask):.1f}" '
        f'stroke="{theme["secondary"]}" stroke-width="1.5" stroke-dasharray="6 5"/>'
    )
    parts.append(
        f'<text x="{WIDTH - RIGHT - 4}" y="{y(mask) - 7:.1f}" font-size="12" text-anchor="end" '
        f'fill="{theme["secondary"]}">10° visibility mask</text>'
    )

    for index, (curve, access) in enumerate(zip(curves, run["station_access"], strict=True)):
        color = theme["series"][index]
        points = " ".join(f"{x(t):.1f},{y(e):.2f}" for t, e in zip(offsets, curve, strict=True))
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" '
            'stroke-linejoin="round" stroke-linecap="round"/>'
        )
        for window in access["windows"]:
            for stamp in (window["start_utc"], window["end_utc"]):
                parts.append(
                    f'<circle cx="{x(seconds_since_start(stamp)):.1f}" cy="{y(mask):.1f}" r="4.5" '
                    f'fill="{color}" stroke="{theme["surface"]}" stroke-width="2"/>'
                )
            peak_x = x(seconds_since_start(window["max_elevation_time_utc"]))
            peak_y = y(window["max_elevation_deg"])
            label_y = peak_y - 12 if index == 0 else peak_y + 22
            parts.append(
                f'<text x="{peak_x:.1f}" y="{label_y:.1f}" font-size="12" text-anchor="middle" '
                f'fill="{theme["ink"]}">{LABELS[index]} · peak {window["max_elevation_deg"]:.1f}°</text>'
            )

    legend_x = LEFT
    for index, label in enumerate(LABELS):
        parts.append(
            f'<line x1="{legend_x}" x2="{legend_x + 18}" y1="78" y2="78" '
            f'stroke="{theme["series"][index]}" stroke-width="3" stroke-linecap="round"/>'
        )
        parts.append(
            f'<text x="{legend_x + 24}" y="82" font-size="12" fill="{theme["secondary"]}">'
            f"{label}</text>"
        )
        legend_x += 170
    parts.append(
        f'<circle cx="{legend_x + 6}" cy="78" r="4.5" fill="{theme["secondary"]}" '
        f'stroke="{theme["surface"]}" stroke-width="2"/>'
    )
    parts.append(
        f'<text x="{legend_x + 16}" y="82" font-size="12" fill="{theme["secondary"]}">'
        "rise / set time found by the tool</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    run = json.loads((EXAMPLE / "run.json").read_text(encoding="utf-8"))
    offsets, curves = sample_curves(EXAMPLE / "config.json")
    for name, theme in THEMES.items():
        destination = OUT / f"vanguard_pass_{name}.svg"
        destination.write_text(draw(theme, offsets, curves, run), encoding="utf-8")
        print(destination.relative_to(ROOT))


if __name__ == "__main__":
    main()
