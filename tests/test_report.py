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


def test_report_has_source_values_units_and_two_real_plots(result) -> None:
    report = render_html(result)
    assert report.count('<svg class="plot"') == 2
    assert "51.22%" in report
    assert "20.49 min" in report
    assert "Duration (s)" in report
    assert "Peak elevation (deg)" in report
    assert "2000-06-27T20:11:00.831787810Z" in report
    assert "2000-06-27T20:31:30.099808909Z" in report
    assert "test-only synthetic zero UT1-UTC/xp/yp" in report
    assert "not a measured pass or an operational prediction" in report
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
    assert "<svg" not in report
