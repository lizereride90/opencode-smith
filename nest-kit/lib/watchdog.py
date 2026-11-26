#!/usr/bin/env python3
"""Quota watchdog. Watches OpenCode logs for a real free-limit line and resets.

Runs on Linux, macOS and Windows. No messages are spent while idle.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
EVENTS = KIT / "logs" / "reset-events.jsonl"
INTERVAL = float(os.environ.get("SMITH_WATCH_INTERVAL", "15"))
COOLDOWN = float(os.environ.get("SMITH_WATCH_COOLDOWN", "600"))

LIMIT_MARKERS = (
    "provider.free-limit",
    "free usage limit reached",
    "freeusagelimerror",
    "you've used today's free messages",
    "used today's free messages",
    "daily free-message limit",
)


def log_paths() -> list[Path]:
    home = Path.home()
    candidates = [
        home / ".local" / "share" / "opencode" / "log" / "opencode.log",
        Path(os.environ.get("XDG_DATA_HOME", home / ".local" / "share"))
        / "opencode" / "log" / "opencode.log",
        Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        / "opencode" / "log" / "opencode.log",
        Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        / "opencode" / "log" / "opencode.log",
    ]
    seen: set[Path] = set()
    out = []
    for path in candidates:
        if path not in seen:
            seen.add(path)
            out.append(path)
    return out


def last_event() -> dict | None:
    if not EVENTS.is_file():
        return None
    lines = [line for line in EVENTS.read_text(encoding="utf-8").splitlines() if line.strip()]
    return json.loads(lines[-1]) if lines else None


def record(event: str, detail: str) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "detail": detail[:600],
    }
    with EVENTS.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def unlimited_command() -> list[str] | None:
    found = shutil.which("opencode-unlimited")
    if found:
        return [found, "reset"]
    candidates = [
        Path.home() / "OpenCode-Unlimited" / "bin" / "opencode-unlimited",
        Path.home() / "Opencode-Unlimited-Limit-Bypass-" / "bin" / "opencode-unlimited",
    ]
    for path in candidates:
        if path.is_file():
            return [str(path), "reset"]
    if os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        for path in local.glob("**/opencode-unlimited.ps1"):
            return ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(path), "reset"]
    return None


def sync_header() -> None:
    configure = Path(__file__).with_name("configure.py")
    if not configure.is_file():
        return
    subprocess.run(
        [sys.executable, str(configure), "--sync-header"],
        capture_output=True, text=True, timeout=60,
    )


def reset() -> bool:
    command = unlimited_command()
    if not command:
        record("reset-failed", "opencode-unlimited not found")
        return False
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        output = (result.stdout + result.stderr).strip()
        record("reset" if result.returncode == 0 else "reset-failed",
               output or f"exit {result.returncode}")
        if result.returncode == 0:
            sync_header()
            record("header-synced", "harness opencode targets updated")
        return result.returncode == 0
    except Exception as exc:
        record("reset-failed", str(exc))
        return False


_positions: dict[Path, int] = {}


def scan() -> str | None:
    # Only inspect bytes appended since the previous poll. Reading the whole
    # tail makes an old limit line trigger a reset every time the loop turns.
    needles = tuple(marker.lower() for marker in LIMIT_MARKERS)
    for path in log_paths():
        if not path.is_file():
            continue
        try:
            size = path.stat().st_size
            if path not in _positions:
                _positions[path] = size
                continue
            if size < _positions[path]:
                _positions[path] = 0
            with path.open("rb") as handle:
                handle.seek(_positions[path])
                chunk = handle.read(size - _positions[path]).decode("utf-8", errors="replace").lower()
                _positions[path] = handle.tell()
        except OSError:
            continue
        for needle in needles:
            if needle in chunk:
                return f"{path.name}: {needle}"
    return None


def main() -> int:
    once = "--once" in sys.argv
    record("watchdog-start", f"interval={INTERVAL}s cooldown={COOLDOWN}s")
    while True:
        hit = scan()
        previous = last_event()
        last_reset = 0.0
        if previous and previous.get("event") in ("reset", "reset-failed"):
            try:
                last_reset = datetime.fromisoformat(previous["at"]).timestamp()
            except (KeyError, ValueError):
                last_reset = 0.0
        if hit and time.time() - last_reset > COOLDOWN:
            record("limit-detected", hit)
            reset()
        if once:
            return 0
        time.sleep(INTERVAL)


if __name__ == "__main__":
    sys.exit(main())
