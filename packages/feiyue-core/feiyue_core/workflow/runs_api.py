from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Sequence
from urllib.parse import unquote, urlparse

from feiyue_core.workflow.execution import RunCatalog, RunEvidenceLoader, RunEvidenceNotFoundError


def create_runs_api_handler(project_root: str | Path) -> type[BaseHTTPRequestHandler]:
    """Create a read-only HTTP handler for persisted Feiyue run evidence."""

    root = Path(project_root)

    class RunsApiHandler(BaseHTTPRequestHandler):
        server_version = "FeiyueRunsAPI/0.1"

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            path = unquote(urlparse(self.path).path).rstrip("/") or "/"
            try:
                if path == "/runs":
                    self._send_json(200, RunCatalog(root).summary().model_dump(mode="json"))
                    return
                if path.startswith("/runs/"):
                    parts = [part for part in path.split("/") if part]
                    if len(parts) == 2:
                        evidence = RunEvidenceLoader(root).load(parts[1])
                        self._send_json(200, evidence.model_dump(mode="json"))
                        return
                    if len(parts) == 3 and parts[2] == "handoff":
                        markdown = RunEvidenceLoader(root).render_handoff_summary(parts[1])
                        self._send_text(200, markdown, content_type="text/markdown; charset=utf-8")
                        return
                self._send_json(404, {"error": "not_found", "path": path})
            except RunEvidenceNotFoundError as exc:
                self._send_json(
                    404,
                    {
                        "error": "run_evidence_not_found",
                        "task_id": exc.task_id,
                        "path": str(exc.path),
                    },
                )

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            self._send_json(405, {"error": "method_not_allowed", "method": "POST"})

        def do_PUT(self) -> None:  # noqa: N802 - stdlib handler API
            self._send_json(405, {"error": "method_not_allowed", "method": "PUT"})

        def do_PATCH(self) -> None:  # noqa: N802 - stdlib handler API
            self._send_json(405, {"error": "method_not_allowed", "method": "PATCH"})

        def do_DELETE(self) -> None:  # noqa: N802 - stdlib handler API
            self._send_json(405, {"error": "method_not_allowed", "method": "DELETE"})

        def log_message(self, format: str, *args: object) -> None:
            return

        def _send_json(self, status: int, payload: object) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, status: int, body_text: str, *, content_type: str) -> None:
            body = body_text.encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return RunsApiHandler


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="feiyue-runs-api",
        description="Serve a read-only local API over Feiyue run evidence.",
    )
    parser.add_argument("--root", default=".", help="Project root containing .hermes/runs")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", default=8765, type=int, help="Bind port")
    args = parser.parse_args(list(argv) if argv is not None else None)

    server = HTTPServer((args.host, args.port), create_runs_api_handler(args.root))
    print(f"Serving Feiyue runs API on http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
