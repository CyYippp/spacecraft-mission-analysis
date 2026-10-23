"""Self-contained, presentation-only HTML report for an analysis result.

The figures draw recorded access intervals. They do not sample an orbit or
calculate new access events, so the JSON result remains the numerical record.
"""

from html import escape
from pathlib import Path

import astropy.units as u
from astropy.time import Time

from .output import result_dict
from .run import AnalysisResult, RunStatus

_BLUE = "#1767b2"
_GREEN = "#158467"
_INK = "#243b53"
_PLOT_LEFT = 220
_PLOT_WIDTH = 840
_SVG_WIDTH = 1100


def _html(value: object) -> str:
    return escape(str(value), quote=True)


def _offset_seconds(timestamp: str, start: Time) -> float:
    time = Time(timestamp.removesuffix("Z"), format="isot", scale="utc")
    return float((time - start).to_value(u.s))


def _tick_label(start: Time, offset_s: float) -> str:
    tick = (start + offset_s * u.s).utc
    tick.precision = 3
    return tick.isot.replace("T", " ") + " UTC"


def _short_label(name: str, limit: int = 29) -> str:
    return name if len(name) <= limit else name[: limit - 1] + "…"


def _table(headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> str:
    head = "".join(f'<th scope="col">{_html(value)}</th>' for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_html(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    return f'<div class="table-scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _access_timeline(result: AnalysisResult, data: dict) -> str:
    station_rows = [
        (item["station_name"], item["windows"], _BLUE if index % 2 == 0 else _GREEN)
        for index, item in enumerate(data["station_access"])
    ]
    union = data["coverage"]["union_intervals"]
    lanes = [*station_rows, ("Any station (union)", union, _INK)]
    start = result.config.start
    span_s = float((result.config.end - start).to_value(u.s))
    axis_y = 55 + len(lanes) * 43
    height = axis_y + 67
    items = [
        f'<svg class="plot" viewBox="0 0 {_SVG_WIDTH} {height}" role="img" '
        'aria-label="Access windows by station and their union over the UTC analysis interval">',
        f'<rect x="{_PLOT_LEFT}" y="28" width="{_PLOT_WIDTH}" height="{axis_y - 28}" fill="#f4f7fa"/>',
    ]
    for tick in range(5):
        x = _PLOT_LEFT + _PLOT_WIDTH * tick / 4
        label = _tick_label(start, span_s * tick / 4)
        items.append(
            f'<line x1="{x:.2f}" y1="28" x2="{x:.2f}" y2="{axis_y}" '
            'stroke="#cbd5df" stroke-dasharray="3 4"/>'
            f'<text x="{x:.2f}" y="{axis_y + 20}" text-anchor="middle" '
            f'class="axis-label">{_html(label)}</text>'
        )
    for index, (name, windows, color) in enumerate(lanes):
        y = 53 + index * 43
        items.append(
            f'<text x="{_PLOT_LEFT - 12}" y="{y + 5}" text-anchor="end" class="lane-label">'
            f"<title>{_html(name)}</title>{_html(_short_label(name))}</text>"
        )
        for window in windows:
            first = _offset_seconds(window["start_utc"], start)
            last = _offset_seconds(window["end_utc"], start)
            x = _PLOT_LEFT + _PLOT_WIDTH * max(0.0, min(1.0, first / span_s))
            right = _PLOT_LEFT + _PLOT_WIDTH * max(0.0, min(1.0, last / span_s))
            width = max(0.0, right - x)
            items.append(
                f'<rect x="{x:.3f}" y="{y - 10}" width="{width:.3f}" height="20" '
                f'fill="{color}"><title>{_html(name)}: '
                f"{_html(window['start_utc'])} to {_html(window['end_utc'])}</title></rect>"
            )
            if "max_elevation_time_utc" in window:
                peak_s = _offset_seconds(window["max_elevation_time_utc"], start)
                peak_x = _PLOT_LEFT + _PLOT_WIDTH * peak_s / span_s
                items.append(
                    f'<circle cx="{peak_x:.3f}" cy="{y}" r="4.5" fill="white" '
                    'stroke="#11263f" stroke-width="1.5">'
                    f"<title>Peak {window['max_elevation_deg']:.2f} deg at "
                    f"{_html(window['max_elevation_time_utc'])}</title></circle>"
                )
        if not windows:
            items.append(
                f'<text x="{_PLOT_LEFT + 9}" y="{y + 5}" class="empty-label">No access</text>'
            )
    items.append(
        f'<text x="{_PLOT_LEFT + _PLOT_WIDTH / 2}" y="{height - 9}" text-anchor="middle" class="axis-title">UTC</text>'
    )
    items.append("</svg>")
    return "".join(items)


def _duration_chart(result: AnalysisResult, data: dict) -> str:
    span_s = float((result.config.end - result.config.start).to_value(u.s))
    rows = [
        (f"{item['station_name']} · window {number}", window["duration_s"], index)
        for index, item in enumerate(data["station_access"])
        for number, window in enumerate(item["windows"], start=1)
    ]
    rows.extend(
        (f"Union interval {number}", interval["duration_s"], None)
        for number, interval in enumerate(data["coverage"]["union_intervals"], start=1)
    )
    if not rows:
        return "<p>No recorded access intervals to compare.</p>"
    axis_y = 48 + len(rows) * 43
    height = axis_y + 48
    items = [
        f'<svg class="plot" viewBox="0 0 {_SVG_WIDTH} {height}" role="img" '
        'aria-label="Duration of each recorded station and union access interval, in minutes">',
        f'<rect x="{_PLOT_LEFT}" y="12" width="{_PLOT_WIDTH}" '
        f'height="{axis_y - 12}" fill="#f4f7fa"/>',
    ]
    for tick in range(5):
        x = _PLOT_LEFT + _PLOT_WIDTH * tick / 4
        minutes = span_s * tick / 240
        items.append(
            f'<line x1="{x:.2f}" y1="12" x2="{x:.2f}" y2="{axis_y}" '
            'stroke="#cbd5df" stroke-dasharray="3 4"/>'
            f'<text x="{x:.2f}" y="{axis_y + 18}" text-anchor="middle" '
            f'class="axis-label">{minutes:.1f}</text>'
        )
    for index, (name, duration_s, station_index) in enumerate(rows):
        y = 28 + index * 43
        color = _INK if station_index is None else (_BLUE if station_index % 2 == 0 else _GREEN)
        width = _PLOT_WIDTH * duration_s / span_s
        label_inside = width > _PLOT_WIDTH - 110
        label_x = _PLOT_LEFT + width - 9 if label_inside else _PLOT_LEFT + width + 9
        label_anchor = "end" if label_inside else "start"
        label_color = "white" if label_inside else _INK
        items.append(
            f'<text x="{_PLOT_LEFT - 12}" y="{y + 5}" text-anchor="end" class="lane-label">'
            f"<title>{_html(name)}</title>{_html(_short_label(name))}</text>"
            f'<rect x="{_PLOT_LEFT}" y="{y - 11}" width="{width:.3f}" height="22" fill="{color}"/>'
            f'<text x="{label_x:.2f}" y="{y + 5}" text-anchor="{label_anchor}" '
            f'fill="{label_color}" class="value-label">{duration_s / 60:.2f} min</text>'
        )
    items.append(
        f'<text x="{_PLOT_LEFT + _PLOT_WIDTH / 2}" y="{height - 8}" '
        'text-anchor="middle" class="axis-title">Duration (min)</text>'
    )
    items.append("</svg>")
    return "".join(items)


def render_html(result: AnalysisResult) -> str:
    """Render existing result data as a standalone report without changing it."""
    data = result_dict(result)
    config = data["configuration"]
    provenance = data["provenance"]
    notices = data["notices"]
    status = data["status"]
    coverage = data["coverage"]
    status_class = {
        RunStatus.SUCCESS: "ok",
        RunStatus.SUCCESS_WITH_WARNINGS: "warning",
        RunStatus.FAILED: "failed",
    }[result.status]
    warnings = [notice for notice in notices if notice["severity"] == "WARNING"]
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Spacecraft access report</title>",
        "<style>",
        "body{font:16px/1.5 system-ui,Segoe UI,sans-serif;color:#172b43;background:#f5f7fa;margin:0}",
        "main{max-width:1200px;margin:auto;padding:28px 34px 64px}h1{font-size:2rem;margin:.2rem 0}",
        "h2{font-size:1.25rem;margin:0 0 1rem}p{margin:.6rem 0}small,.muted{color:#526276}",
        "section{background:white;border:1px solid #d8e1e9;border-radius:10px;padding:22px;margin:20px 0}",
        ".lead{font-size:1.08rem}.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-weight:700}",
        ".ok{background:#ddf3e9;color:#135f47}.warning{background:#fff0c2;color:#714c00}",
        ".failed{background:#fce4e0;color:#9b3428}",
        ".metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}",
        ".metric{border:1px solid #d8e1e9;border-radius:8px;padding:15px}.metric strong{display:block;font-size:1.5rem}",
        ".table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}",
        "th,td{border-bottom:1px solid #e3e9ef;padding:9px 11px;text-align:left;vertical-align:top}",
        "th{background:#eff3f7;color:#243b53;white-space:nowrap}td{overflow-wrap:anywhere}",
        ".plot{width:100%;height:auto;display:block}.axis-label{font:10px system-ui;fill:#526276}",
        ".axis-title,.lane-label{font:13px system-ui;fill:#243b53}.value-label{font:13px system-ui}",
        ".empty-label{font:12px system-ui;fill:#67798d}.note{background:#fff9e9;border-left:4px solid #b57a1a;padding:12px 16px}",
        ".warning-summary{background:#fff4d6;border:1px solid #d89b2b;border-left:5px solid #b57a1a;border-radius:6px;padding:12px 16px;margin:16px 0}",
        ".warning-summary ul{margin:6px 0 0;padding-left:22px}",
        "a{color:#135d9c}@media print{body{background:white}main{padding:0}section{break-inside:avoid;border-color:#b8c2cd}}",
        "</style></head><body><main>",
        "<header><h1>Spacecraft access report</h1>",
        '<p class="lead">Geometric station access and temporal coverage from an archived TLE.</p>',
        f'<p><span class="badge {status_class}">{_html(status)}</span> '
        f"&nbsp; Schema {_html(data['schema_version'])} &nbsp;·&nbsp; "
        f"spacecraft-mission-analysis {_html(provenance['project_version'])}</p></header>",
        '<p class="note">Calculated model output, not a measured pass or an operational prediction. '
        "Visibility is modelled geometrically only. Finite event-discovery sampling can miss "
        "narrow or grazing access. TLE age and Earth-orientation input also limit validity. "
        "See run.json for full numerical precision.</p>",
    ]
    if warnings:
        parts.append(
            '<aside class="warning-summary" role="alert"><strong>'
            f"{len(warnings)} warning{'s' if len(warnings) != 1 else ''} for this run</strong>"
            "<ul>"
            + "".join(
                f"<li><strong>{_html(notice['code'])}</strong>: {_html(notice['message'])}</li>"
                for notice in warnings
            )
            + "</ul></aside>"
        )
    if coverage is None:
        parts.append(
            "<section><h2>Analysis result</h2><p>No access or coverage results were produced. "
            "Review the notices below; plots are omitted for failed runs.</p></section>"
        )
    else:
        parts.extend(
            [
                '<section><h2>Run summary</h2><div class="metrics">',
                f'<div class="metric">Total access<strong>{coverage["total_access_duration_s"] / 60:.2f} min</strong></div>',
                f'<div class="metric">Temporal coverage<strong>{coverage["coverage_fraction"] * 100:.2f}%</strong></div>',
                f'<div class="metric">Longest no-access gap<strong>{coverage["longest_no_access_gap_s"] / 60:.2f} min</strong></div>',
                f'<div class="metric">Merged access intervals<strong>{coverage["merged_access_interval_count"]}</strong></div>',
                "</div></section>",
                '<section><h2>Access timeline</h2><p class="muted">Horizontal position is UTC. '
                "Bars show intervals at or above the configured elevation mask; dots mark reported peaks. "
                "The dark row is the union across stations.</p>",
                _access_timeline(result, data),
                "</section>",
                '<section><h2>Recorded window durations</h2><p class="muted">'
                "Each bar is one reported station window or merged union interval. "
                "Overlapping station windows are not added to obtain the union.</p>",
                _duration_chart(result, data),
                "</section>",
                "<section><h2>Access windows</h2>",
            ]
        )
        window_rows = []
        for station in data["station_access"]:
            for window in station["windows"]:
                clipping = (
                    ", ".join(
                        label
                        for label, clipped in (
                            ("start clipped", window["start_clipped"]),
                            ("end clipped", window["end_clipped"]),
                        )
                        if clipped
                    )
                    or "—"
                )
                window_rows.append(
                    (
                        station["station_name"],
                        window["start_utc"],
                        window["end_utc"],
                        f"{window['duration_s']:.3f}",
                        window["max_elevation_time_utc"],
                        f"{window['max_elevation_deg']:.3f}",
                        clipping,
                    )
                )
        parts.append(
            _table(
                (
                    "Station",
                    "Start (UTC)",
                    "End (UTC)",
                    "Duration (s)",
                    "Peak time (UTC)",
                    "Peak elevation (deg)",
                    "Boundary",
                ),
                window_rows,
            )
            if window_rows
            else "<p>No station access windows in the analysis interval.</p>"
        )
        parts.append("</section><section><h2>Combined coverage</h2>")
        parts.append(
            _table(
                ("Start (UTC)", "End (UTC)", "Duration (s)"),
                [
                    (item["start_utc"], item["end_utc"], f"{item['duration_s']:.3f}")
                    for item in coverage["union_intervals"]
                ],
            )
            if coverage["union_intervals"]
            else "<p>No combined access intervals.</p>"
        )
        parts.append("</section>")
    parts.append("<section><h2>Inputs and provenance</h2>")
    parts.append("<h3>Ground stations (WGS84)</h3>")
    parts.append(
        _table(
            (
                "Station",
                "Latitude (deg; north positive)",
                "Longitude (deg; east positive)",
                "Ellipsoidal height (m)",
            ),
            [
                (
                    station["name"],
                    station["latitude_deg"],
                    station["longitude_deg_east"],
                    station["ellipsoidal_height_m"],
                )
                for station in config["stations"]
            ],
        )
    )
    parts.append("<h3>Run configuration</h3>")
    parts.append(
        _table(
            ("Item", "Value"),
            [
                ("Analysis start (UTC)", config["analysis_start_utc"]),
                ("Analysis end (UTC)", config["analysis_end_utc"]),
                ("TLE catalogue ID", config["tle"]["catalog_id"]),
                ("TLE epoch (UTC)", config["tle"]["epoch_utc"]),
                ("TLE source", config["tle"]["source"]),
                ("Minimum elevation (deg)", config["minimum_elevation_deg"]),
                ("Station count", len(config["stations"])),
                ("Event discovery step (s)", config["coarse_step_s"]),
                ("Root tolerance (s)", config["root_tolerance_s"]),
                ("Earth-orientation mode", config["earth_orientation_mode"]),
                ("Earth-orientation source", config["earth_orientation_source"]),
                (
                    "Earth-orientation table SHA-256",
                    config["earth_orientation_table_sha256"] or "—",
                ),
                ("Source revision", config["source_revision"] or "—"),
                (
                    "SGP4 version / gravity constants",
                    f"{provenance['sgp4_version']} / {provenance['sgp4_gravity_constants']}",
                ),
                (
                    "Astropy / SciPy versions",
                    f"{provenance['astropy_version']} / {provenance['scipy_version']}",
                ),
                (
                    "Orbit frame / station ellipsoid",
                    f"{provenance['sgp4_output_frame']} / {provenance['station_ellipsoid']}",
                ),
            ],
        )
    )
    parts.append("</section><section><h2>Notices</h2>")
    parts.append(
        _table(
            ("Severity", "Code", "Stage", "Message"),
            [(n["severity"], n["code"], n["stage"], n["message"]) for n in notices],
        )
        if notices
        else "<p>No notices were emitted for this run.</p>"
    )
    parts.append(
        "</section><section><h2>Machine-readable evidence</h2><p>"
        '<a href="run.json">Full JSON result</a> · '
        '<a href="csv/access_windows.csv">Access windows CSV</a> · '
        '<a href="csv/coverage.csv">Coverage CSV</a> · '
        '<a href="csv/warnings.csv">Notices CSV</a></p></section>'
        "</main></body></html>\n"
    )
    return "".join(parts)


def write_html(result: AnalysisResult, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html(result), encoding="utf-8", newline="\n")
    return target
