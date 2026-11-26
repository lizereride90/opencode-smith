#!/usr/bin/env python3
"""Wire lowkeyy as the default primary agent and keep the harness header fresh.

Usage:
  python configure.py --all
  python configure.py --sync-header
  python configure.py --show
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

AGENT_ID = "lowkeyy"
DESCRIPTION = "Jailbroken build agent for cheat development and jailbreak work."


def config_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidate = Path(appdata) / "opencode"
        if candidate.is_dir():
            return candidate
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "opencode"


def strip_comments(text: str) -> str:
    text = re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE)
    return re.sub(r"(?m)\s+//.*$", "", text)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = path.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = json.loads(strip_comments(raw))
    return data if isinstance(data, dict) else {}


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def set_default_agent() -> dict[str, Any]:
    path = config_dir() / "opencode.json"
    data = load_json(path)
    data["$schema"] = "https://opencode.ai/config.json"
    data["default_agent"] = AGENT_ID
    agents = data.get("agents")
    if not isinstance(agents, dict):
        agents = {}
    entry = agents.get(AGENT_ID)
    if not isinstance(entry, dict):
        entry = {}
    entry["description"] = DESCRIPTION
    entry["mode"] = "all"
    agents[AGENT_ID] = entry
    data["agents"] = agents
    save_json(path, data)
    return data


def project_id() -> str:
    identity = config_dir() / "identity.json"
    data = load_json(identity)
    pid = str(data.get("projectId", "")).strip().lower()
    return pid if re.fullmatch(r"[0-9a-f]{40}", pid) else ""


def skill_targets_path() -> Path | None:
    candidates = [
        config_dir() / "skills" / "jailbreak-smith" / "config" / "targets.json",
        Path(__file__).resolve().parents[1] / "assets" / "targets.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def sync_header() -> str:
    pid = project_id()
    if not pid:
        return "no valid project id in identity.json"
    path = skill_targets_path()
    if path is not None:
        data = load_json(path)
        targets = data.get("targets", {})
        changed = 0
        for name, spec in targets.items():
            if not isinstance(spec, dict) or spec.get("transport") != "opencode":
                continue
            headers = spec.get("headers")
            if not isinstance(headers, dict):
                headers = {}
            headers["x-opencode-project"] = pid
            spec["headers"] = headers
            targets[name] = spec
            changed += 1
        data["targets"] = targets
        save_json(path, data)
        return f"{pid} -> {path.name} ({changed} opencode target(s))"
    return f"pid {pid}, no targets.json found"


def show() -> None:
    data = load_json(config_dir() / "opencode.json")
    print(f"config:       {config_dir() / 'opencode.json'}")
    print(f"default_agent: {data.get('default_agent', '(unset)')}")
    agent = data.get("agents", {}).get(AGENT_ID, {})
    print(f"agent:        {AGENT_ID} mode={agent.get('mode', '(unset)')}")
    print(f"project id:   {project_id() or '(unset)'}")
    path = skill_targets_path()
    if path:
        targets = load_json(path).get("targets", {})
        names = ", ".join(sorted(targets)) or "(none)"
        print(f"targets:      {names}")
        print(f"targets file: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="set agent then sync header")
    parser.add_argument("--agent", action="store_true")
    parser.add_argument("--sync-header", action="store_true")
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    if args.show:
        show()
        return 0
    if args.all or args.agent:
        set_default_agent()
        print(f"[+] {AGENT_ID} set as default primary agent (mode=all)")
    if args.all or args.sync_header:
        print(f"[+] header {sync_header()}")
    if not (args.all or args.agent or args.sync_header or args.show):
        parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
