from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from .errors import EConfigError, InputValidationError
from .service import ConfigurationService


MAX_BODY_BYTES = 1024 * 1024


class EConfigApplication:
    def __init__(self, service: ConfigurationService | None = None) -> None:
        self.service = service or ConfigurationService()

    def handle(
        self, method: str, path: str, body: Any = None
    ) -> tuple[int, dict[str, Any]]:
        try:
            if method == "GET" and path == "/health":
                connection = self.service.connection_info()
                return 200, {
                    "status": "ok",
                    "service": "econfig-quick-config",
                    "profile": "power-9080-heu-quick-v2",
                    "ibm": connection,
                }
            if method == "GET" and path == "/v1/options":
                return 200, self.service.options()
            if method == "POST" and path in {
                "/v1/requests/preview",
                "/v1/configurations/plan",
            }:
                return 200, self.service.preview(self._require_object(body))
            if method == "POST" and path in {
                "/v1/requests/generate",
                "/v1/configurations/generate",
            }:
                return 200, self.service.generate(self._require_object(body))
            return 404, {"error": {"code": "not_found", "message": "경로를 찾지 못했습니다."}}
        except EConfigError as exc:
            return exc.status, exc.to_dict()
        except Exception:
            return 500, {
                "error": {
                    "code": "internal_error",
                    "message": "처리 중 내부 오류가 발생했습니다.",
                }
            }

    @staticmethod
    def _require_object(body: Any) -> Mapping[str, Any]:
        if not isinstance(body, Mapping):
            raise InputValidationError("JSON object 본문이 필요합니다.")
        return body


class _Handler(BaseHTTPRequestHandler):
    application: EConfigApplication

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch(None)

    def do_POST(self) -> None:  # noqa: N802
        length_text = self.headers.get("Content-Length", "0")
        try:
            length = int(length_text)
        except ValueError:
            self._send(400, {"error": {"code": "invalid_length", "message": "잘못된 Content-Length입니다."}})
            return
        if length > MAX_BODY_BYTES:
            self._send(413, {"error": {"code": "body_too_large", "message": "요청 본문이 너무 큽니다."}})
            return
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, {"error": {"code": "invalid_json", "message": "유효한 UTF-8 JSON이 필요합니다."}})
            return
        self._dispatch(body)

    def _dispatch(self, body: Any) -> None:
        path = urlsplit(self.path).path
        if self.command == "GET" and path in {"/", "/index.html"}:
            html = (Path(__file__).with_name("web") / "index.html").read_bytes()
            self._send_bytes(200, html, "text/html; charset=utf-8")
            return
        if self.command == "GET" and path == "/favicon.ico":
            self._send_bytes(204, b"", "image/x-icon")
            return
        status, response = self.application.handle(self.command, path, body)
        self._send(status, response)

    def _send(self, status: int, response: dict[str, Any]) -> None:
        encoded = json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._send_bytes(status, encoded, "application/json; charset=utf-8")

    def _send_bytes(self, status: int, encoded: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: Any) -> None:
        # Never log request bodies or IBM credentials from the local tool.
        return


def create_server(
    host: str,
    port: int,
    application: EConfigApplication,
) -> ThreadingHTTPServer:
    handler = type("EConfigHandler", (_Handler,), {"application": application})
    return ThreadingHTTPServer((host, port), handler)

