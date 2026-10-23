"""Loopback-only browser controls for the existing analysis command and report."""

import argparse
import html
import json
import re
import secrets
import sys
import traceback
import webbrowser
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .cli import _write_outputs
from .input import InputConfigError, load_analysis_config
from .run import run_analysis

_RUN_ID = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{12}\Z")
_CSV_FILES = frozenset(
    {
        "run.csv",
        "stations.csv",
        "access_windows.csv",
        "coverage.csv",
        "union_intervals.csv",
        "warnings.csv",
    }
)


def _record(run_id: str, data: dict) -> dict:
    coverage = data["coverage"]
    return {
        "id": run_id,
        "status": data["status"],
        "coverage_fraction": coverage["coverage_fraction"] if coverage else None,
        "window_count": sum(len(station["windows"]) for station in data["station_access"] or []),
        "notice_count": len(data["notices"]),
    }


def _default_config(cwd: Path) -> Path | None:
    candidates = (
        cwd / "examples" / "vanguard_run" / "config.json",
        Path(__file__).resolve().parents[2] / "examples" / "vanguard_run" / "config.json",
    )
    return next((path.resolve() for path in candidates if path.is_file()), None)


class DashboardServer(HTTPServer):
    """Single-run local server; one request runs at a time to protect model state."""

    def __init__(
        self,
        *,
        config_path: Path | None = None,
        output_root: Path,
        cwd: Path | None = None,
        port: int = 0,
        token: str | None = None,
    ) -> None:
        self.cwd = (cwd or Path.cwd()).resolve()
        self.config_path = (
            config_path.resolve() if config_path is not None else _default_config(self.cwd)
        )
        self.output_root = output_root.resolve()
        self.token = token or secrets.token_urlsafe(24)
        super().__init__(("127.0.0.1", port), _DashboardHandler)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_port}/{self.token}/"

    def runs(self) -> list[dict]:
        if not self.output_root.is_dir():
            return []
        records = []
        for directory in sorted(self.output_root.iterdir(), reverse=True):
            if (
                not _RUN_ID.fullmatch(directory.name)
                or not directory.is_dir()
                or directory.is_symlink()
            ):
                continue
            try:
                run_json = directory / "run.json"
                report = directory / "report.html"
                if run_json.is_symlink() or report.is_symlink() or not report.is_file():
                    continue
                records.append(
                    _record(directory.name, json.loads(run_json.read_text(encoding="utf-8")))
                )
            except (OSError, ValueError, KeyError, TypeError):
                continue
            if len(records) == 20:
                break
        return records


class _DashboardHandler(BaseHTTPRequestHandler):
    server: DashboardServer

    def _route(self) -> str | None:
        path = urlsplit(self.path).path
        prefix = f"/{self.server.token}/"
        return path[len(prefix) :] if path.startswith(prefix) else None

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
            "connect-src 'self'; frame-src 'self'; frame-ancestors 'self'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, value: dict | list) -> None:
        self._send(code, json.dumps(value).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        route = self._route()
        if route == "":
            template = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")
            page = template.replace(
                "{{CONFIG_PATH}}", html.escape(str(self.server.config_path or ""), quote=True)
            ).replace("{{OUTPUT_ROOT}}", html.escape(str(self.server.output_root)))
            self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")
            return
        if route == "api/runs":
            self._json(200, self.server.runs())
            return
        parts = route.split("/") if route is not None else []
        if len(parts) >= 3 and parts[0] == "runs" and _RUN_ID.fullmatch(parts[1]):
            name = "/".join(parts[2:])
            if name in {"report.html", "run.json"} or (
                len(parts) == 4 and parts[2] == "csv" and parts[3] in _CSV_FILES
            ):
                directory = self.server.output_root / parts[1]
                if directory.is_symlink() or (directory / "csv").is_symlink():
                    self.send_error(404)
                    return
                file = directory / name
                if file.is_symlink():
                    self.send_error(404)
                    return
                try:
                    body = file.read_bytes()
                except OSError:
                    self.send_error(404)
                    return
                content_type = (
                    "text/html; charset=utf-8"
                    if name == "report.html"
                    else "application/json; charset=utf-8"
                    if name == "run.json"
                    else "text/csv; charset=utf-8"
                )
                self._send(200, body, content_type)
                return
        self.send_error(404)

    def do_POST(self) -> None:
        if self._route() != "api/run":
            self.send_error(404)
            return
        origin = self.headers.get("Origin")
        if origin is not None and origin != f"http://127.0.0.1:{self.server.server_port}":
            self._json(403, {"error": "The run request must come from this local dashboard."})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            self._json(415, {"error": "Expected a JSON run request."})
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
            if not 0 < length <= 4096:
                raise ValueError
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict) or set(request) != {"config_path"}:
                raise ValueError
            raw_path = request["config_path"]
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise ValueError
        except (ValueError, UnicodeError):
            self._json(400, {"error": "Choose a configuration JSON file before running."})
            return
        try:
            path = Path(raw_path).expanduser()
            if not path.is_absolute():
                path = self.server.cwd / path
            config = load_analysis_config(path)
        except (InputConfigError, ValueError) as exc:
            self._json(400, {"error": f"Configuration error: {exc}"})
            return
        try:
            result = run_analysis(config)
            run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(6)
            output_dir = self.server.output_root / run_id
            _write_outputs(result, output_dir)
            record = _record(
                run_id, json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
            )
        except OSError as exc:
            self._json(500, {"error": f"Could not save the analysis: {exc}"})
            return
        except Exception:
            traceback.print_exc()
            self._json(500, {"error": "The analysis stopped unexpectedly; see the server log."})
            return
        self._json(200, record)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Open a local analysis dashboard")
    parser.add_argument("--config", type=Path, help="default analysis JSON (editable in dashboard)")
    parser.add_argument(
        "--output-root", type=Path, default=Path("outputs/dashboard-runs"), help="new run folders"
    )
    parser.add_argument("--port", type=int, default=0, help="local port (default: automatic)")
    parser.add_argument(
        "--no-browser", action="store_true", help="print the URL without opening it"
    )
    args = parser.parse_args(argv)
    try:
        server = DashboardServer(
            config_path=args.config, output_root=args.output_root, port=args.port
        )
    except OSError as exc:
        print(f"dashboard startup error: {exc}", file=sys.stderr)
        return 4
    print(f"Local dashboard: {server.url}", flush=True)
    print("Press Ctrl+C to stop. Each run saves a new evidence folder.", flush=True)
    if not args.no_browser:
        webbrowser.open(server.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
