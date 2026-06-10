#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import plugin_manager as manager


HOST = os.environ.get("PLUGIN_MANAGER_HOST", "127.0.0.1")
PORT = int(os.environ.get("PLUGIN_MANAGER_PORT", "8765"))
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, data: object, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _error(self, message: str, status: int = 400) -> None:
        self._json({"error": message}, status)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/state":
                self._json(manager.state())
                return
            if parsed.path == "/api/plugins":
                self._json({"plugins": manager.state()["plugins"]})
                return
            if parsed.path == "/api/projects":
                self._json({"projects": manager.load_project_map()})
                return
            if parsed.path == "/api/backups":
                self._json({"backups": manager.backups()})
                return
            if parsed.path == "/api/audit":
                self._json({"audit": manager.audit_events()})
                return
            self._static(parsed.path)
        except Exception as exc:
            self._error(str(exc), 500)

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        path = "/index.html" if parsed.path == "/" else parsed.path
        target = (FRONTEND_DIR / path.lstrip("/")).resolve()
        if not str(target).startswith(str(FRONTEND_DIR.resolve())) or not target.exists():
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(target.stat().st_size))
        self.end_headers()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path == "/api/projects/refresh":
                self._json({"projects": manager.infer_project_plugins()})
                return
            if parsed.path == "/api/restart-codex":
                self._json(manager.restart_codex(dry_run=bool(payload.get("dryRun"))))
                return
            if parsed.path == "/api/backups/restore":
                self._json(manager.restore_backup(payload.get("name", "latest")))
                return
            if parsed.path.startswith("/api/profiles/") and parsed.path.endswith("/apply"):
                profile = parsed.path.split("/")[3]
                self._json(manager.apply_profile(profile))
                return
            self._error("Unknown endpoint", 404)
        except Exception as exc:
            self._error(str(exc), 500)

    def do_PATCH(self) -> None:
        parsed = urlparse(self.path)
        try:
            payload = self._read_json()
            if parsed.path.startswith("/api/plugins/"):
                plugin = parsed.path.split("/")[-1]
                self._json(manager.toggle_plugin(plugin, bool(payload.get("enabled"))))
                return
            self._error("Unknown endpoint", 404)
        except Exception as exc:
            self._error(str(exc), 500)

    def _static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        target = (FRONTEND_DIR / path.lstrip("/")).resolve()
        if not str(target).startswith(str(FRONTEND_DIR.resolve())) or not target.exists():
            self._error("Not found", 404)
            return
        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def main() -> None:
    manager.ensure_dirs()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"PluginManager dashboard: http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
