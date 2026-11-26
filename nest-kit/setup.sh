#!/usr/bin/env bash
# NEST // 4080 — one-shot setup for OpenCode, Unlimited, lowkeyy and the skill.
set -uo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
OC_BIN="$HOME/.opencode/bin"
UNLIMITED_DIR=""

say()  { printf '  \033[90m%s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m[+]\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m[!]\033[0m %s\n' "$1"; }
head() { printf '\n==> %s\n' "$1"; }

head "nest // 4080"
say "kit: $KIT"
say "config: $CONFIG"

# ---------------------------------------------------------------- 1. python
head "python"
if command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
  ok "python3: $($PY --version 2>&1)"
else
  warn "python3 missing — config helper, watchdog and UI need it"
  PY=""
fi

# ---------------------------------------------------------------- 2. opencode
head "opencode"
export PATH="$OC_BIN:$PATH"
if [ -x "$OC_BIN/opencode" ]; then
  ok "found $($OC_BIN/opencode --version 2>/dev/null)"
elif command -v opencode >/dev/null 2>&1; then
  ok "found $(opencode --version 2>/dev/null)"
else
  say "installing from opencode.ai"
  if curl -fsSL https://opencode.ai/install 2>/dev/null | bash; then
    ok "installer finished"
  else
    warn "installer failed — install OpenCode by hand and rerun"
  fi
  export PATH="$OC_BIN:$PATH"
fi
[ -x "$OC_BIN/opencode" ] && ok "cli at $OC_BIN/opencode" || warn "cli not found yet"

# ---------------------------------------------------------------- 3. unlimited
head "opencode unlimited"
for candidate in \
  "$HOME/OpenCode-Unlimited" \
  "$KIT/../OpenCode-Unlimited" \
  "$HOME/Opencode-Unlimited-Limit-Bypass-"; do
  if [ -f "$candidate/install.sh" ]; then UNLIMITED_DIR="$candidate"; break; fi
done

if [ -z "$UNLIMITED_DIR" ]; then
  say "cloning Tazmyan/OpenCode-Unlimited"
  if command -v git >/dev/null 2>&1; then
    git clone --depth 1 https://github.com/Tazmyan/OpenCode-Unlimited.git "$HOME/OpenCode-Unlimited" 2>/dev/null \
      && UNLIMITED_DIR="$HOME/OpenCode-Unlimited" \
      || warn "clone failed"
  else
    warn "git missing — cannot clone Unlimited"
  fi
fi

if [ -n "$UNLIMITED_DIR" ]; then
  ok "source: $UNLIMITED_DIR"
  (cd "$UNLIMITED_DIR" && bash ./install.sh) || warn "unlimited install had errors"
  UNLIMITED_BIN="$UNLIMITED_DIR/bin/opencode-unlimited"
  [ -x "$UNLIMITED_BIN" ] && export PATH="$UNLIMITED_DIR/bin:$PATH"
  if command -v opencode-unlimited >/dev/null 2>&1; then
    timeout 180 opencode-unlimited on -NoProbe -KeepRoute >/dev/null 2>&1 \
      && ok "unlimited armed (no probe, route untouched)" \
      || say "automatic 'on' skipped — watchdog below handles resets"
  fi
else
  warn "unlimited not installed; quota resets may be unavailable"
fi

# ---------------------------------------------------------------- 4. agent
head "lowkeyy agent"
mkdir -p "$CONFIG/agents"
if [ -f "$KIT/assets/lowkeyy.md" ]; then
  cp -f "$KIT/assets/lowkeyy.md" "$CONFIG/agents/lowkeyy.md"
  ok "agent installed: $CONFIG/agents/lowkeyy.md"
else
  warn "assets/lowkeyy.md missing"
fi

if [ -n "$PY" ] && [ -f "$KIT/lib/configure.py" ]; then
  "$PY" "$KIT/lib/configure.py" --all || warn "config helper had errors"
  "$PY" "$KIT/lib/configure.py" --show
fi

# ---------------------------------------------------------------- 5. skill
head "jailbreak-smith skill"
mkdir -p "$CONFIG/skills"
if [ -f "$KIT/assets/jailbreak-smith.zip" ]; then
  TMP="$(mktemp -d)"
  if command -v unzip >/dev/null 2>&1; then
    unzip -q "$KIT/assets/jailbreak-smith.zip" -d "$TMP"
  else
    "$PY" -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
      "$KIT/assets/jailbreak-smith.zip" "$TMP"
  fi
  rm -rf "$CONFIG/skills/jailbreak-smith"
  cp -R "$TMP/jailbreak-smith/skill" "$CONFIG/skills/jailbreak-smith"
  rm -rf "$TMP"
  ok "skill installed: $CONFIG/skills/jailbreak-smith"
else
  warn "assets/jailbreak-smith.zip missing"
fi

# ---------------------------------------------------------------- 6. watchdog
head "quota watchdog"
mkdir -p "$KIT/logs"
if [ -n "$PY" ] && [ -f "$KIT/lib/watchdog.py" ]; then
  EXISTING="$(cat "$KIT/logs/watchdog.pid" 2>/dev/null || true)"
  if [ -n "$EXISTING" ] && kill -0 "$EXISTING" 2>/dev/null; then
    ok "watchdog already running (pid $EXISTING)"
  else
    nohup "$PY" "$KIT/lib/watchdog.py" >>"$KIT/logs/watchdog.out" 2>&1 &
    echo $! > "$KIT/logs/watchdog.pid"
    ok "watchdog running (pid $(cat "$KIT/logs/watchdog.pid"))"
  fi
else
  warn "watchdog not started"
fi

# ---------------------------------------------------------------- 7. ui choice
head "web interface"
if [ -n "${NEST_WEB:-}" ]; then
  ANSWER="$NEST_WEB"
  say "web interface choice from NEST_WEB: $ANSWER"
else
  printf '  Install the localhost web interface? [y/N] '
  read -r ANSWER </dev/tty || ANSWER=""
fi
case "${ANSWER,,}" in
  y|yes)
    if [ -z "$PY" ]; then
      warn "python3 missing — UI cannot start"
    else
      PORT="${NEST_UI_PORT:-8787}"
      if curl -fsS "http://127.0.0.1:$PORT/api/status" >/dev/null 2>&1; then
        ok "web UI already answering on http://127.0.0.1:$PORT"
      else
        nohup "$PY" "$KIT/web/server.py" --host 127.0.0.1 --port "$PORT" \
          >>"$KIT/logs/web.out" 2>&1 &
        echo $! > "$KIT/logs/web.pid"
        ok "web UI on http://127.0.0.1:$PORT"
      fi
      sleep 2
      curl -fsS "http://127.0.0.1:$PORT/api/status" >/dev/null 2>&1 \
        && ok "UI answered a status check" \
        || warn "UI started but did not answer yet — see $KIT/logs/web.out"
    fi
    ;;
  *)
    ok "setup complete — terminal only"
    ;;
esac

# ---------------------------------------------------------------- tutorial
head "how to use it"
cat <<'TUTORIAL'
  1. Open a terminal and run:  opencode
  2. lowkeyy is the default agent. Switch model with /model; Big Pickle is
     listed as "Big Pickle" under the OpenCode provider.
  3. Just talk. The watchdog watches the log and rotates the project id
     automatically when a free-limit line lands.
  4. Manual reset:   opencode-unlimited reset
  5. Skill commands (inside OpenCode):
       @skill:jailbreak-smith
       python ~/.config/opencode/skills/jailbreak-smith/scripts/smith.py targets
       python ~/.config/opencode/skills/jailbreak-smith/scripts/smith.py study big-pickle
       python ~/.config/opencode/skills/jailbreak-smith/scripts/smith.py payloads
  6. Web UI (if installed): http://127.0.0.1:8787
       /  - OpenCode commands, including Unlimited
       @  - skills, including jailbreak-smith
       settings - reset usage, theme, text size, timestamps

  7. Manage it with:  smith {start|stop|info|uninstall|donate}

  Logs live in:  KIT/logs/
TUTORIAL
printf '\n  '
ok "nest is warm. go gnaw."
printf '\n'
