"""Local dashboard routes reuse the existing scientific and evidence contracts."""

import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from spacecraft_mission_analysis.dashboard import DashboardServer

EXAMPLE = Path(__file__).parent.parent / "examples" / "vanguard_run"
CONFIG = EXAMPLE / "config.json"
CSV_NAMES = {
    "run.csv",
    "stations.csv",
    "access_windows.csv",
    "coverage.csv",
    "union_intervals.csv",
    "warnings.csv",
}


@pytest.fixture
def dashboard(tmp_path: Path):
    server = DashboardServer(
        config_path=CONFIG,
        output_root=tmp_path / "runs",
        cwd=tmp_path,
        token="local-test-token",
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def _request(server: DashboardServer, route: str, payload: dict | None = None, **headers):
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        server.url + route,
        data=body,
        headers={"Content-Type": "application/json", **headers},
    )
    with urlopen(request, timeout=30) as response:
        return response.status, response.read(), response.headers


def test_run_button_backend_saves_existing_result_and_report(dashboard: DashboardServer) -> None:
    code, page, headers = _request(dashboard, "")
    assert code == 200
    assert headers["Content-Security-Policy"]
    assert b"Run analysis" in page
    assert str(CONFIG).encode("utf-8") in page
    assert b"test-only Earth-orientation table" in page
    assert json.loads(_request(dashboard, "api/runs")[1]) == []

    code, body, _ = _request(
        dashboard,
        "api/run",
        {"config_path": str(CONFIG)},
        Origin=f"http://127.0.0.1:{dashboard.server_port}",
    )
    record = json.loads(body)
    assert code == 200
    assert record["status"] == "SUCCESS"
    assert record["window_count"] == 2
    assert record["notice_count"] == 0
    assert record["coverage_fraction"] == 0.5121950087914875

    directory = dashboard.output_root / record["id"]
    assert {item.name for item in directory.iterdir()} == {"run.json", "report.html", "csv"}
    assert {item.name for item in (directory / "csv").iterdir()} == CSV_NAMES
    data = json.loads((directory / "run.json").read_text(encoding="utf-8"))
    assert data["provenance"]["project_version"] == "0.1.1"
    assert data["coverage"]["coverage_fraction"] == record["coverage_fraction"]
    assert json.loads(_request(dashboard, "api/runs")[1]) == [record]
    assert b"Access timeline" in _request(dashboard, f"runs/{record['id']}/report.html")[1]
    assert json.loads(_request(dashboard, f"runs/{record['id']}/run.json")[1]) == data
    assert b"station_name" in _request(dashboard, f"runs/{record['id']}/csv/access_windows.csv")[1]


def test_invalid_input_and_foreign_origin_do_not_publish(dashboard: DashboardServer) -> None:
    with pytest.raises(HTTPError) as wrong_origin:
        _request(
            dashboard,
            "api/run",
            {"config_path": str(CONFIG)},
            Origin="https://another-site.example",
        )
    assert wrong_origin.value.code == 403

    with pytest.raises(HTTPError) as invalid:
        _request(dashboard, "api/run", {"config_path": "missing.json"})
    assert invalid.value.code == 400
    assert b"Configuration error" in invalid.value.read()
    assert not dashboard.output_root.exists()

    with pytest.raises(HTTPError) as wrong_token:
        with urlopen(f"http://127.0.0.1:{dashboard.server_port}/wrong/api/runs"):
            pass
    assert wrong_token.value.code == 404
    with pytest.raises(HTTPError) as traversal:
        _request(dashboard, "runs/../../examples/vanguard_run/config.json")
    assert traversal.value.code == 404
