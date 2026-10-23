"""Self-contained, presentation-only HTML report for an analysis result.

The figures draw recorded access intervals. They do not sample an orbit or
calculate new access events, so the JSON result remains the numerical record.
"""

from html import escape
from math import ceil
from pathlib import Path

import astropy.units as u
from astropy.time import Time

from .output import result_dict
from .run import AnalysisResult, RunStatus

_BLUE = "#236176"
_GREEN = "#16836f"
_INK = "#263e54"
_PLOT_LEFT = 338
_PLOT_WIDTH = 722
_SVG_WIDTH = 1100


def _html(value: object) -> str:
    return escape(str(value), quote=True)


def _offset_seconds(timestamp: str, start: Time) -> float:
    time = Time(timestamp.removesuffix("Z"), format="isot", scale="utc")
    return float((time - start).to_value(u.s))


def _short_label(name: str, limit: int = 48) -> str:
    return name if len(name) <= limit else name[: limit - 1] + "…"


def _display_time(timestamp: str) -> str:
    """Round HTML timestamps for reading; run.json retains the exact value."""
    value = Time(timestamp.removesuffix("Z"), format="isot", scale="utc")
    value.precision = 1
    return value.isot.replace("T", " ")


def _display_duration(seconds: float) -> str:
    tenths = round(seconds * 10)
    minutes, remaining = divmod(tenths, 600)
    return f"{minutes}:{remaining / 10:04.1f}"


def _facts(rows: list[tuple[str, object]]) -> str:
    return (
        '<dl class="facts">'
        + "".join(
            f"<div><dt>{_html(label)}</dt><dd>{_html(value)}</dd></div>" for label, value in rows
        )
        + "</dl>"
    )


def _table(
    headers: tuple[str, ...], rows: list[tuple[object, ...]], *, time_columns: bool = False
) -> str:
    head = "".join(f'<th scope="col">{_html(value)}</th>' for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_html(value)}</td>" for value in row) + "</tr>" for row in rows
    )
    kind = " time-table" if time_columns else ""
    return f'<div class="table-scroll{kind}"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _access_timeline(result: AnalysisResult, data: dict) -> str:
    station_rows = [
        (item["station_name"], item["windows"], _BLUE if index % 2 == 0 else _GREEN)
        for index, item in enumerate(data["station_access"])
    ]
    union = data["coverage"]["union_intervals"]
    lanes = [*station_rows, ("Any station (union)", union, _INK)]
    start = result.config.start
    span_s = float((result.config.end - start).to_value(u.s))
    axis_y = 42 + len(lanes) * 36
    height = axis_y + 47
    items = [
        f'<svg class="plot" viewBox="0 0 {_SVG_WIDTH} {height}" role="img" '
        'aria-label="Access windows by station and their union over the UTC analysis interval">',
        f'<rect x="{_PLOT_LEFT}" y="22" width="{_PLOT_WIDTH}" height="{axis_y - 22}" fill="#f2f6f6"/>',
    ]
    for tick in range(5):
        x = _PLOT_LEFT + _PLOT_WIDTH * tick / 4
        minutes = span_s * tick / 240
        label = f"{minutes:g}"
        anchor = "start" if tick == 0 else "end" if tick == 4 else "middle"
        items.append(
            f'<line x1="{x:.2f}" y1="22" x2="{x:.2f}" y2="{axis_y}" '
            'stroke="#cad8dc" stroke-dasharray="3 4"/>'
            f'<text x="{x:.2f}" y="{axis_y + 18}" text-anchor="{anchor}" '
            f'class="axis-label">{_html(label)}</text>'
        )
    for index, (name, windows, color) in enumerate(lanes):
        y = 43 + index * 36
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
                f'<rect x="{x:.3f}" y="{y - 9}" width="{width:.3f}" height="18" rx="2" '
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
        f'<text x="{_PLOT_LEFT + _PLOT_WIDTH / 2}" y="{height - 7}" text-anchor="middle" class="axis-title">Minutes from analysis start</text>'
    )
    items.append("</svg>")
    return "".join(items)


def _duration_chart(data: dict) -> str:
    rows = [
        (
            item["station_name"]
            if len(item["windows"]) == 1
            else f"{item['station_name']} · window {number}",
            window["duration_s"],
            index,
        )
        for index, item in enumerate(data["station_access"])
        for number, window in enumerate(item["windows"], start=1)
    ]
    rows.extend(
        (f"Union interval {number}", interval["duration_s"], None)
        for number, interval in enumerate(data["coverage"]["union_intervals"], start=1)
    )
    if not rows:
        return "<p>No recorded access intervals to compare.</p>"
    span_s = max(300, ceil(max(row[1] for row in rows) / 300) * 300)
    left, width, svg_width = 310, 350, 772
    axis_y = 35 + len(rows) * 33
    height = axis_y + 42
    items = [
        f'<svg class="plot" viewBox="0 0 {svg_width} {height}" role="img" '
        'aria-label="Duration of each recorded station and union access interval, in minutes">',
        f'<rect x="{left}" y="12" width="{width}" height="{axis_y - 12}" fill="#f2f6f6"/>',
    ]
    max_minutes = int(span_s / 60)
    for minutes in range(0, max_minutes + 1, 5):
        x = left + width * minutes / max_minutes
        anchor = "start" if minutes == 0 else "end" if minutes == max_minutes else "middle"
        items.append(
            f'<line x1="{x:.2f}" y1="12" x2="{x:.2f}" y2="{axis_y}" '
            'stroke="#cad8dc" stroke-dasharray="3 4"/>'
            f'<text x="{x:.2f}" y="{axis_y + 18}" text-anchor="{anchor}" '
            f'class="axis-label">{minutes:g}</text>'
        )
    for index, (name, duration_s, station_index) in enumerate(rows):
        y = 27 + index * 33
        color = _INK if station_index is None else (_BLUE if station_index % 2 == 0 else _GREEN)
        bar_width = width * duration_s / span_s
        label_inside = bar_width > width - 90
        label_x = left + bar_width - 8 if label_inside else left + bar_width + 8
        label_anchor = "end" if label_inside else "start"
        label_color = "white" if label_inside else _INK
        items.append(
            f'<text x="{left - 10}" y="{y + 4}" text-anchor="end" class="lane-label">'
            f"<title>{_html(name)}</title>{_html(_short_label(name, 50))}</text>"
            f'<rect x="{left}" y="{y - 9}" width="{bar_width:.3f}" height="18" rx="2" fill="{color}"/>'
            f'<text x="{label_x:.2f}" y="{y + 5}" text-anchor="{label_anchor}" '
            f'fill="{label_color}" class="value-label">{duration_s / 60:.2f} min</text>'
        )
    items.append(
        f'<text x="{left + width / 2}" y="{height - 6}" '
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
    errors = [notice for notice in notices if notice["severity"] == "ERROR"]
    interval = (
        f"{_display_time(config['analysis_start_utc'])}–"
        f"{_display_time(config['analysis_end_utc'])} UTC"
    )
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Spacecraft access report</title>",
        "<style>",
        ":root{color-scheme:light}*{box-sizing:border-box}body{font:14px/1.48 system-ui,Segoe UI,sans-serif;color:#263b4c;background:#e9eff0;margin:0}",
        "main{max-width:1120px;min-height:100vh;margin:auto;padding:28px 40px 36px;background:#fff;border-top:5px solid #163a50;box-shadow:0 7px 30px #18344314}",
        "h1,h2,h3,p{margin-top:0}h1{font-size:1.82rem;line-height:1.15;letter-spacing:-.03em;margin:.1rem 0 .35rem;color:#183a50}h2{font-size:1.14rem;color:#183a50;margin:0 0 .35rem}h3{font-size:.92rem;color:#183a50;margin:0 0 .45rem}",
        "p{margin-bottom:.6rem}.muted{color:#526777}.eyebrow{font-size:.7rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:#16836f;margin:0 0 .55rem}",
        "header{padding-bottom:16px;border-bottom:1px solid #cbd8dc}.header-row{display:flex;justify-content:space-between;gap:22px;align-items:flex-start}.subtitle{color:#526777;margin:0}.run-state{text-align:right;white-space:nowrap}.run-state p{font-size:.78rem;color:#526777;margin:.4rem 0 0}.context{display:flex;flex-wrap:wrap;gap:5px 20px;margin-top:15px;color:#40596a;font-size:.81rem}",
        ".badge{display:inline-block;padding:3px 9px;border-radius:3px;font-size:.72rem;letter-spacing:.04em;font-weight:800}.ok{background:#dcedeb;color:#176254}.warning{background:#fff0c2;color:#714c00}.failed{background:#fce4e0;color:#9b3428}",
        "section{padding:18px 0;border-bottom:1px solid #d7e1e4}.section-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:9px}.section-head p{margin:0;font-size:.81rem}.plot{width:100%;height:auto;display:block}.axis-label{font:12px system-ui;fill:#526777}.axis-title,.lane-label{font:13px system-ui;fill:#263e54}.value-label{font:12px system-ui}.empty-label{font:12px system-ui;fill:#667b88}",
        ".purpose-band{display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:15px 0 10px}.purpose-band p{font-size:.83rem;color:#40596a;margin:0}",
        ".note{margin:14px 0 0;padding:9px 12px;background:#f1f6f6;border-left:3px solid #16836f;color:#38505e;font-size:.82rem}.warning-summary,.error-summary{background:#fff4d6;border-left:4px solid #b57a1a;padding:10px 13px;margin:12px 0 0}.error-summary{background:#fce9e5;border-color:#ac493a}.warning-summary ul,.error-summary ul{margin:5px 0 0;padding-left:20px}",
        ".analysis-grid{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(245px,.7fr);gap:22px;align-items:start}.chart-panel,.summary-panel{min-width:0}.summary-panel{border-left:1px solid #d7e1e4;padding-left:19px}.metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.metric{border-top:2px solid #b5c9cc;padding:6px 3px;font-size:.75rem;color:#526777}.metric strong{display:block;font-size:1.23rem;line-height:1.2;color:#183a50;font-variant-numeric:tabular-nums}.microcopy{font-size:.78rem;color:#526777;margin:9px 0 0}.scroll-cue{display:none}",
        ".table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:.81rem}th,td{border-bottom:1px solid #e1e9eb;padding:7px 8px;text-align:left;vertical-align:top}th{background:#f0f5f5;color:#2e4c5b;white-space:nowrap;font-size:.72rem;text-transform:uppercase;letter-spacing:.03em}td{overflow-wrap:anywhere}.time-table td:nth-child(2),.time-table td:nth-child(3),.time-table td:nth-child(5){white-space:nowrap}.table-note{font-size:.78rem;color:#526777;margin:5px 0 9px}details{margin-top:10px;border-top:1px solid #e1e9eb;padding-top:9px}summary{cursor:pointer;color:#236176;font-weight:700}details p{font-size:.78rem;color:#526777}",
        ".detail-grid{display:grid;grid-template-columns:1fr 1fr;gap:26px}.facts{margin:0}.facts>div{display:grid;grid-template-columns:minmax(125px,.9fr) minmax(0,1.1fr);gap:10px;padding:5px 0;border-bottom:1px solid #e7eded;font-size:.8rem}.facts dt{color:#526777}.facts dd{margin:0;font-weight:600;overflow-wrap:anywhere}.station-table{margin-top:12px}.station-table h3{margin-bottom:5px}.repro{margin-top:13px}.no-notices{font-size:.79rem;color:#526777;padding:9px 0}.evidence{display:flex;flex-wrap:wrap;align-items:center;gap:5px 15px;padding-top:15px;font-size:.79rem}.evidence strong{color:#183a50;margin-right:5px}a{color:#176879;text-underline-offset:2px}",
        "@media(max-width:740px){main{padding:22px 18px 30px}.analysis-grid,.detail-grid,.purpose-band{grid-template-columns:1fr}.purpose-band{gap:12px}.summary-panel{border-left:0;border-top:1px solid #d7e1e4;padding:12px 0 0}.header-row{display:block}.run-state{text-align:left;margin-top:10px}.section-head{display:block}.scroll-cue{display:block;color:#526777;font-size:.75rem;margin:5px 0 0}.timeline-plot .plot{min-width:900px}.chart-panel .plot{min-width:680px}.timeline-plot,.chart-panel{overflow-x:auto}.time-table table{min-width:900px}.facts>div{grid-template-columns:145px minmax(0,1fr)}}",
        "@page{size:A4 landscape;margin:10mm}@media print{body{background:#fff;font-size:10px}main{max-width:none;min-height:0;padding:0;border-top:3px solid #163a50;box-shadow:none}header{padding-bottom:8px}.context{margin-top:8px}section{padding:6px 0}h2{font-size:1.05rem}h3{font-size:.86rem}.purpose-band{padding:7px 0 4px;gap:18px}.note{margin-top:8px;padding:7px 10px}.microcopy{margin:4px 0}.table-note{margin:3px 0 6px}.analysis-grid{grid-template-columns:1.2fr .8fr;gap:14px;padding:3px 0;break-inside:avoid}.analysis-grid .metric{padding:2px 1px}.analysis-grid .microcopy{margin:3px 0 0}.plot{min-width:0}.timeline-plot{max-width:930px;margin:auto}.timeline-plot,.chart-panel,.table-scroll{overflow:visible}.time-table td:first-child{white-space:nowrap}th,td{padding:3px 5px}.facts>div{padding:2px 0}.station-table{margin-top:5px}.repro{margin-top:5px}.no-notices{padding:3px 0}.evidence{padding-top:4px}thead{display:table-header-group}tr,.metric,.facts>div{break-inside:avoid}section,details{break-inside:auto}.note,.warning-summary,.error-summary{print-color-adjust:exact}.evidence a{color:#263b4c}}",
        "@media print{header{padding-bottom:5px}.context{margin-top:5px}.purpose-band{padding:4px 0 2px}.purpose-band p,.note{line-height:1.35}.note{margin-top:5px;padding:5px 8px}.timeline-plot{max-width:850px}.analysis-grid .metric{padding:0}.analysis-grid .microcopy{line-height:1.3}}",
        "</style></head><body><main>",
        '<header><p class="eyebrow">Mission analysis / run report</p><div class="header-row"><div>'
        '<h1>Spacecraft access report</h1><p class="subtitle">Geometric station access and temporal coverage from an archived TLE.</p></div>',
        f'<div class="run-state"><span class="badge {status_class}">{_html(status)}</span>'
        f"<p>v{_html(provenance['project_version'])} · schema {_html(data['schema_version'])}</p></div></div>",
        f'<div class="context"><span>Catalogue {_html(config["tle"]["catalog_id"])}</span>'
        f"<span>{_html(len(config['stations']))} stations</span>"
        f"<span>Mask {_html(config['minimum_elevation_deg'])}°</span>"
        f"<span>{_html(interval)}</span></div></header>",
        '<section class="purpose-band" aria-label="Project purpose and engineering use">'
        "<div><h2>What this project does</h2><p>It propagates an archived Two-Line Element (TLE) "
        "and reports when fixed ground stations exceed an elevation mask, plus their combined "
        "geometric coverage of the chosen UTC interval.</p></div>"
        "<div><h2>Engineering use</h2><p>These outputs can inform early ground-station and "
        "data-handling trade studies. This archived demonstration is not an operations product; "
        "operational planning needs current inputs and separate validation.</p>"
        "</div></section>",
        '<p class="note">Calculated model output, not a measured pass or an operational prediction. '
        "Visibility is modelled geometrically only. Finite event-discovery sampling can miss "
        "narrow or grazing access. TLE age and Earth-orientation input also limit validity. "
        "Exact numerical values are in run.json.</p>",
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
    if errors:
        parts.append(
            '<aside class="error-summary" role="alert"><strong>'
            f"{len(errors)} error{'s' if len(errors) != 1 else ''} for this run</strong>"
            "<ul>"
            + "".join(
                f"<li><strong>{_html(notice['code'])}</strong>: {_html(notice['message'])}</li>"
                for notice in errors
            )
            + "</ul></aside>"
        )
    if coverage is None:
        parts.append(
            "<section><h2>Analysis result</h2><p>No access or coverage results were produced. "
            "Review the notices below to identify the failure stage; plots are omitted for failed runs.</p></section>"
        )
    else:
        parts.extend(
            [
                '<section><div class="section-head"><h2>Access timeline</h2>'
                '<p class="muted">Relative minutes · exact UTC interval in run context above</p></div>',
                '<p class="microcopy">Each station row shows when calculated elevation exceeds the mask. '
                "Dots mark the calculated peak within each window; the dark union row shows when at least "
                "one station exceeds the mask.</p>"
                '<p class="scroll-cue">Scroll charts and tables horizontally on narrow screens.</p>'
                '<div class="timeline-plot">',
                _access_timeline(result, data),
                '</div></section><section class="analysis-grid"><div class="chart-panel">'
                '<h2>Recorded durations</h2><p class="microcopy">Each bar is one station window or merged '
                "network interval. Length represents geometric access time, not usable downlink time.</p>",
                _duration_chart(data),
                '</div><div class="summary-panel"><h2>Pass &amp; network summary</h2><div class="metrics">',
                f'<div class="metric">Total access<strong>{coverage["total_access_duration_s"] / 60:.2f} min</strong></div>',
                f'<div class="metric">Temporal coverage<strong>{coverage["coverage_fraction"] * 100:.2f}%</strong></div>',
                f'<div class="metric">Longest no-access gap<strong>{coverage["longest_no_access_gap_s"] / 60:.2f} min</strong></div>',
                f'<div class="metric">Merged intervals<strong>{coverage["merged_access_interval_count"]}</strong></div>',
                '</div><p class="microcopy">Coverage is the share of the interval with any station '
                "above the mask; overlap counts once. The longest gap has none.</p></div></section>",
                '<section class="access-section"><h2>Access windows</h2><p class="table-note">'
                "Start and end are threshold crossings or analysis-boundary clips. Peak is the "
                "highest calculated elevation in that window; boundary flags identify clips. "
                "Displayed UTC times are rounded to 0.1 s "
                "and durations to 0.1 s. See run.json for exact nanosecond timestamps and full numerical precision.</p>",
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
                        _display_time(window["start_utc"]),
                        _display_time(window["end_utc"]),
                        _display_duration(window["duration_s"]),
                        f"{_display_time(window['max_elevation_time_utc'])} / {window['max_elevation_deg']:.1f}°",
                        clipping,
                    )
                )
        parts.append(
            _table(
                (
                    "Station",
                    "Start (UTC)",
                    "End (UTC)",
                    "Duration (min:s)",
                    "Peak (UTC / deg)",
                    "Boundary",
                ),
                window_rows,
                time_columns=True,
            )
            if window_rows
            else "<p>No station access windows in the analysis interval.</p>"
        )
        parts.append(
            f'<details class="coverage-details"><summary>Combined coverage intervals '
            f"({len(coverage['union_intervals'])})</summary>"
        )
        parts.append(
            '<p class="table-note">Each interval is continuous geometric access from at least '
            "one station; overlapping or touching station windows are merged.</p>"
        )
        parts.append(
            _table(
                ("Start (UTC)", "End (UTC)", "Duration (min:s)"),
                [
                    (
                        _display_time(item["start_utc"]),
                        _display_time(item["end_utc"]),
                        _display_duration(item["duration_s"]),
                    )
                    for item in coverage["union_intervals"]
                ],
                time_columns=True,
            )
            if coverage["union_intervals"]
            else "<p>No combined access intervals.</p>"
        )
        parts.append("</details></section>")
    parts.append(
        '<section><h2>Scenario &amp; model</h2><p class="table-note">Scenario fields define '
        "what was analysed. Model settings and provenance show how access was calculated and "
        "help a reviewer reproduce it; station coordinates are fixed WGS84 inputs.</p>"
        '<div class="detail-grid"><div>'
    )
    parts.append("<h3>Scenario</h3>")
    parts.append(
        _facts(
            [
                ("TLE catalogue ID", config["tle"]["catalog_id"]),
                ("TLE epoch (UTC)", _display_time(config["tle"]["epoch_utc"])),
                ("Minimum elevation", f"{config['minimum_elevation_deg']}°"),
                ("Station count", len(config["stations"])),
            ]
        )
    )
    parts.append("</div><div><h3>Model &amp; provenance</h3>")
    parts.append(
        _facts(
            [
                ("Event discovery step", f"{config['coarse_step_s']} s"),
                ("Root tolerance", f"{config['root_tolerance_s']} s"),
                ("Earth orientation", config["earth_orientation_mode"]),
                (
                    "SGP4 / gravity constants",
                    f"{provenance['sgp4_version']} / {provenance['sgp4_gravity_constants']}",
                ),
                (
                    "Astropy / SciPy",
                    f"{provenance['astropy_version']} / {provenance['scipy_version']}",
                ),
                (
                    "Orbit frame / ellipsoid",
                    f"{provenance['sgp4_output_frame']} / {provenance['station_ellipsoid']}",
                ),
            ]
        )
    )
    parts.append('</div></div><div class="station-table"><h3>Ground stations · WGS84</h3>')
    parts.append(
        _table(
            (
                "Station",
                "Latitude (° N)",
                "Longitude (° E)",
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
    parts.append('</div><details class="repro"><summary>Reproducibility details</summary>')
    parts.append(
        _facts(
            [
                ("Analysis start (UTC)", config["analysis_start_utc"]),
                ("Analysis end (UTC)", config["analysis_end_utc"]),
                ("TLE epoch (UTC)", config["tle"]["epoch_utc"]),
                ("TLE source", config["tle"]["source"]),
                ("Earth-orientation source", config["earth_orientation_source"]),
                (
                    "Earth-orientation table SHA-256",
                    config["earth_orientation_table_sha256"] or "—",
                ),
                ("Source revision", config["source_revision"] or "—"),
            ],
        )
    )
    parts.append("</details></section>")
    if notices:
        parts.append(
            '<section><h2>Notices</h2><p class="table-note">Review these conditions and '
            "their stages before interpreting the result.</p>"
        )
        parts.append(
            _table(
                ("Severity", "Code", "Stage", "Message"),
                [(n["severity"], n["code"], n["stage"], n["message"]) for n in notices],
            )
        )
        parts.append("</section>")
    else:
        parts.append(
            '<p class="no-notices">Notices · None emitted for this run. '
            "This does not establish physical accuracy or operational suitability.</p>"
        )
    parts.append(
        '<footer class="evidence"><strong>Machine-readable evidence</strong>'
        '<a href="run.json">Full JSON result</a>'
        '<a href="csv/access_windows.csv">Access windows CSV</a>'
        '<a href="csv/coverage.csv">Coverage CSV</a>'
        '<a href="csv/warnings.csv">Notices CSV</a></footer>'
        "</main></body></html>\n"
    )
    return "".join(parts)


def write_html(result: AnalysisResult, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html(result), encoding="utf-8", newline="\n")
    return target
