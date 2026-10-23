"""Human-readable report checks separate from scientific result verification."""

from dataclasses import replace
from pathlib import Path

import pytest

from spacecraft_mission_analysis import (
    RunNotice,
    RunStatus,
    compute_temporal_coverage,
    load_analysis_config,
    run_analysis,
)
from spacecraft_mission_analysis.report import render_html
from spacecraft_mission_analysis.run import StationAccess

CONFIG = Path(__file__).parent.parent / "examples" / "vanguard_run" / "config.json"


@pytest.fixture(scope="module")
def result():
    return run_analysis(load_analysis_config(CONFIG))


def test_report_presents_archived_values_without_changing_precision_source(result) -> None:
    report = render_html(result)
    assert report.count('<svg class="plot"') == 2
    assert "51.22%" in report
    assert "20.49 min" in report
    assert "Duration (min:s)" in report
    assert "Peak (UTC / deg)" in report
    assert "2000-06-27 20:11:00.8" in report
    assert "2000-06-27 20:31:30.1" in report
    assert "exact nanosecond timestamps" in report
    assert "2000-06-27T20:11:00.831787810Z" in report
    assert "2000-06-27T20:31:30.099808909Z" in report
    assert "<td>2000-06-27T" not in report
    assert report.count(">Equator Greenwich synthetic fixed WGS84 station</text>") == 2
    assert "test-only synthetic zero UT1-UTC/xp/yp" in report
    assert "What this project does" in report
    assert "Engineering use" in report
    assert "operational planning needs current inputs and separate validation" in report
    assert "the dark union row shows when at least one station exceeds the mask" in report
    assert "not usable downlink time" in report
    assert "Coverage is the share of the interval" in report
    assert "Start and end are threshold crossings or analysis-boundary clips" in report
    assert "Scenario fields define what was analysed" in report
    assert "not a measured pass or an operational prediction" in report
    assert "Finite event-discovery sampling can miss narrow or grazing access" in report
    assert "Visibility is modelled geometrically only" in report
    assert "Duration (min)" in report
    for tick in ("0", "10", "20", "30", "40"):
        assert f'class="axis-label">{tick}</text>' in report
    assert "Minutes from analysis start" in report
    assert "Reproducibility details" in report
    assert "Earth-orientation table SHA-256" in report
    assert "Combined coverage intervals (1)" in report
    assert "Notices · None emitted for this run." in report
    assert "This does not establish physical accuracy or operational suitability" in report
    assert "<h2>Notices</h2>" not in report
    assert '<a href="run.json">' in report
    assert "<script" not in report


def test_report_escapes_notice_text(result) -> None:
    dangerous = '<img src=x onerror="alert(1)">'
    altered = replace(
        result,
        status=RunStatus.SUCCESS_WITH_WARNINGS,
        notices=(RunNotice("TEST_WARNING", "WARNING", "report", dangerous),),
    )
    report = render_html(altered)
    assert dangerous not in report
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;" in report
    assert '<span class="badge warning">SUCCESS_WITH_WARNINGS</span>' in report
    assert '<aside class="warning-summary" role="alert">' in report
    assert "1 warning for this run" in report
    assert report.index("1 warning for this run") < report.index("Access timeline")
    assert report.count("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;") == 2


def test_successful_no_pass_is_shown_as_zero_coverage(result) -> None:
    empty = replace(
        result,
        station_access=tuple(StationAccess(station, ()) for station in result.config.stations),
        coverage=compute_temporal_coverage(result.config.start, result.config.end, ()),
    )
    report = render_html(empty)
    assert "0.00%" in report
    assert "No station access windows in the analysis interval" in report
    assert "No combined access intervals" in report
    assert report.count("No access</text>") == len(result.config.stations) + 1


def test_failed_run_has_notice_and_no_plots(result) -> None:
    failure = replace(
        result,
        status=RunStatus.FAILED,
        notices=(RunNotice("SGP4_PROPAGATION_ERROR", "ERROR", "propagation", "example"),),
        station_access=None,
        coverage=None,
    )
    report = render_html(failure)
    assert "No access or coverage results were produced" in report
    assert "SGP4_PROPAGATION_ERROR" in report
    assert '<aside class="error-summary" role="alert">' in report
    assert "<svg" not in report
