#!/usr/bin/env python3
"""Chat API for the nest. Binds to 127.0.0.1 only."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

KIT = Path(__file__).resolve().parents[1]
WEB = KIT / "web"
sys.path.insert(0, str(KIT / "lib"))

import configure  # noqa: E402
import watchdog  # noqa: E402

PORT = int(os.environ.get("NEST_UI_PORT", "8787"))
STARTED = time.time()


def run(command: list[str], timeout: int = 300) -> tuple[int, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
        return result.returncode, (result.stdout + result.stderr).strip()
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except Exception as exc:
        return 1, str(exc)


def api(method: str, path: str, body: dict[str, Any] | None = None,
        timeout: int = 300) -> tuple[int, Any]:
    command = ["opencode", "api", method, path]
    if body is not None:
        command += ["--data", json.dumps(body, ensure_ascii=False)]
    code, raw = run(command, timeout=timeout)
    if code != 0:
        return code, raw
    if not raw.strip():
        return 0, {}
    try:
        payload = json.loads(raw)
        return 0, payload.get("data", payload) if isinstance(payload, dict) else payload
    except json.JSONDecodeError:
        return 1, "bad response"


def model_ref(model: str) -> dict[str, str]:
    if model.startswith("free/"):
        return {"id": model, "providerID": "apinex"}
    if "/" in model:
        provider, model_id = model.split("/", 1)
        return {"id": model_id, "providerID": provider}
    return {"id": model, "providerID": "opencode"}


def text_of(message: dict[str, Any]) -> str:
    parts = []
    direct = message.get("text")
    if isinstance(direct, str) and direct:
        parts.append(direct)
    payload = message.get("payload")
    if isinstance(payload, dict) and isinstance(payload.get("text"), str):
        parts.append(payload["text"])
    for part in message.get("content", []) or []:
        if part.get("type") == "text" and part.get("text"):
            parts.append(str(part["text"]))
    return "\n".join(parts)


def status() -> dict[str, Any]:
    config = configure.load_json(configure.config_dir() / "opencode.json")
    code, raw = run(["opencode", "--version"], timeout=30)
    skill = configure.config_dir() / "skills" / "jailbreak-smith"
    return {
        "version": raw.strip() if code == 0 else "(unavailable)",
        "default_agent": config.get("default_agent", "(unset)"),
        "agent_mode": config.get("agents", {}).get("lowkeyy", {}).get("mode", "(unset)"),
        "project_id": configure.project_id(),
        "limit_detected": watchdog.scan(),
        "smith_ready": skill.is_dir() and (skill / "SKILL.md").is_file(),
        "uptime_s": int(time.time() - STARTED),
    }


def commands() -> list[dict[str, str]]:
    code, data = api("get", "/api/command")
    if code != 0 or not isinstance(data, list):
        return []
    return [
        {"name": str(item.get("name", "")),
         "description": str(item.get("description", ""))}
        for item in data if item.get("name")
    ]


def skills() -> list[dict[str, str]]:
    code, data = api("get", "/api/skill")
    if code != 0 or not isinstance(data, list):
        return []
    return [
        {"id": str(item.get("id", "")),
         "name": str(item.get("name") or item.get("id", "")),
         "description": str(item.get("description", ""))}
        for item in data if item.get("id")
    ]


def models() -> list[dict[str, Any]]:
    code, data = api("get", "/api/model")
    if code != 0 or not isinstance(data, list):
        return []
    out = [
        {
            "id": str(item.get("id", "")),
            "name": str(item.get("name") or item.get("id", "")),
            "providerID": str(item.get("providerID", "")),
            "context": (item.get("limit") or {}).get("context", 0),
        }
        for item in data
        if item.get("type") == "chat" and item.get("enabled") is not False
    ]
    return sorted(out, key=lambda m: m["id"])


def sessions() -> list[dict[str, Any]]:
    code, data = api("get", "/api/session?limit=20")
    if code != 0 or not isinstance(data, list):
        return []
    out = []
    for item in data:
        updated = (item.get("time") or {}).get("updated", 0)
        out.append({
            "id": item.get("id", ""),
            "title": item.get("title") or "untitled",
            "updated": updated,
        })
    return sorted(out, key=lambda x: x["updated"], reverse=True)


def messages(session_id: str) -> list[dict[str, Any]]:
    code, data = api("get", f"/api/session/{session_id}/message")
    if code != 0 or not isinstance(data, list):
        return []
    out = []
    for item in data:
        kind = item.get("type")
        if kind not in ("user", "assistant"):
            continue
        out.append({"role": kind, "text": text_of(item)})
    return out


def new_session(title: str, model: str, agent: str | None) -> tuple[str, str]:
    body: dict[str, Any] = {"title": title[:48] or "nest chat", "model": model_ref(model)}
    if agent:
        body["agent"] = agent
    code, data = api("post", "/api/session", body)
    if code != 0 or not isinstance(data, dict):
        return "", str(data)
    session_id = data.get("id", "")
    return session_id, "" if session_id else "no session id"


def collect(session_id: str, sent_ok: bool, failure: str) -> dict[str, Any]:
    if not sent_ok:
        return {"ok": False, "error": failure, "sessionID": session_id}
    api("post", f"/api/experimental/session/{session_id}/wait", {}, timeout=600)
    code, data = api("get", f"/api/session/{session_id}/message")
    if code != 0 or not isinstance(data, list):
        return {"ok": False, "error": "could not read response", "sessionID": session_id}
    assistants = [item for item in data if item.get("type") == "assistant"]
    if not assistants:
        return {"ok": False, "error": "no assistant response", "sessionID": session_id}

    def created(item: dict[str, Any]) -> int:
        return int((item.get("time") or {}).get("created", 0))

    newest = max(assistants, key=created)
    error = newest.get("error")
    if error:
        detail = str(error.get("message", error)) if isinstance(error, dict) else str(error)
        kind = str(error.get("type", "")) if isinstance(error, dict) else ""
        quota_hit = "free-limit" in kind or "limit" in detail.lower() or "429" in detail
        if quota_hit:
            watchdog.record("limit-detected", detail[:400])
            watchdog.reset()
        return {"ok": False, "error": detail, "reset": quota_hit, "sessionID": session_id}

    # A skill mention can produce a tool-call turn followed by the real answer.
    # Take the newest assistant message that actually has text.
    with_text = [(created(item), text_of(item)) for item in assistants if text_of(item)]
    if with_text:
        return {"ok": True, "text": max(with_text, key=lambda pair: pair[0])[1],
                "sessionID": session_id}
    return {"ok": False, "error": "no assistant response", "sessionID": session_id}


def chat(text: str, model: str, agent: str | None, session_id: str | None) -> dict[str, Any]:
    if not session_id:
        session_id, error = new_session(text, model, agent)
        if error:
            return {"ok": False, "error": error}
    code, _ = api("post", f"/api/session/{session_id}/prompt", {"text": text})
    return collect(session_id, code == 0, "prompt failed")


def run_command(name: str, text: str, model: str, agent: str | None,
                session_id: str | None) -> dict[str, Any]:
    if not session_id:
        session_id, error = new_session(f"/{name}", model, agent)
        if error:
            return {"ok": False, "error": error}
    code, _ = api("post", f"/api/session/{session_id}/command",
                  {"name": name, "text": text})
    return collect(session_id, code == 0, "command failed")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_: Any) -> None:
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: Any, code: int = 200) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        try:
            data = json.loads(self.rfile.read(length))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _static(self, name: str) -> None:
        path = WEB / name
        if not path.is_file():
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
        }
        self._send(200, path.read_bytes(), types.get(path.suffix, "application/octet-stream"))

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            path = "/index.html"
        if path in ("/index.html", "/styles.css", "/app.js"):
            self._static(path.lstrip("/"))
            return
        if path == "/api/status":
            self._json(status())
            return
        if path == "/api/sessions":
            self._json(sessions())
            return
        if path == "/api/commands":
            self._json(commands())
            return
        if path == "/api/models":
            self._json(models())
            return
        if path == "/api/skills":
            self._json(skills())
            return
        if path.startswith("/api/session/"):
            session_id = path[len("/api/session/"):]
            if "/" in session_id or ".." in session_id:
                self._json({"error": "bad id"}, 400)
                return
            self._json(messages(session_id))
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        body = self._body()
        if path == "/api/chat":
            text = str(body.get("text", "")).strip()
            if not text:
                self._json({"ok": False, "error": "empty prompt"}, 400)
                return
            self._json(chat(
                text,
                str(body.get("model") or "big-pickle"),
                body.get("agent") or None,
                body.get("session_id") or None,
            ))
            return
        if path == "/api/command":
            name = str(body.get("name", "")).strip().lstrip("/")
            if not name:
                self._json({"ok": False, "error": "no command"}, 400)
                return
            self._json(run_command(
                name,
                str(body.get("text", "")),
                str(body.get("model") or "big-pickle"),
                body.get("agent") or "lowkeyy",
                body.get("session_id") or None,
            ))
            return
        if path == "/api/reset":
            ok = watchdog.reset()
            self._json({"ok": ok})
            return
        if path == "/api/sync-header":
            configure.sync_header()
            self._json({"ok": True, "project_id": configure.project_id()})
            return
        self._send(404, b"not found", "text/plain; charset=utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"nest chat on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
