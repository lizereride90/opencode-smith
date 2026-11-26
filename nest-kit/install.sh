#!/usr/bin/env bash
# curl installer for NEST // 4080. Fetches the kit, installs `smith`, runs setup.
set -euo pipefail

DEST="${SMITH_HOME:-$HOME/.local/share/smith-kit}"
BIN="${SMITH_BIN:-$HOME/.local/bin}"
KIT_URL="${SMITH_KIT_URL:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"

say() { printf '  \033[90m%s\033[0m\n' "$1"; }
ok()  { printf '  \033[32m[+]\033[0m %s\n' "$1"; }
bad() { printf '  \033[31m[x]\033[0m %s\n' "$1" >&2; exit 1; }

echo "==> nest // 4080 installer"

PY="$(command -v python3 || command -v py || true)"
[ -n "$PY" ] || bad "python3 required"

TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT

if [ -n "$KIT_URL" ]; then
  say "fetching kit from $KIT_URL"
  curl -fsSL "$KIT_URL" -o "$TEMP/nest-kit.zip" || bad "download failed"
elif [ -f "$HERE/nest-kit.zip" ]; then
  say "using local kit: $HERE/nest-kit.zip"
  cp "$HERE/nest-kit.zip" "$TEMP/nest-kit.zip"
elif [ -f "$HERE/../nest-kit.zip" ]; then
  say "using local kit: $HERE/../nest-kit.zip"
  cp "$HERE/../nest-kit.zip" "$TEMP/nest-kit.zip"
else
  bad "no kit found. set SMITH_KIT_URL to the nest-kit.zip URL, or run install.sh from the kit directory"
fi

if command -v unzip >/dev/null 2>&1; then
  unzip -q "$TEMP/nest-kit.zip" -d "$TEMP/extract" || bad "unzip failed"
else
  "$PY" -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
    "$TEMP/nest-kit.zip" "$TEMP/extract" || bad "extract failed"
fi

SOURCE="$TEMP/extract/nest-kit"
[ -f "$SOURCE/setup.sh" ] || bad "bad kit: setup.sh missing"

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
cp -R "$SOURCE" "$DEST"
ok "kit at $DEST"

mkdir -p "$BIN"
ln -sf "$DEST/bin/smith" "$BIN/smith"
chmod +x "$DEST/bin/smith" "$DEST/setup.sh"
ok "command installed: $BIN/smith"

case ":$PATH:" in
  *":$BIN:"*) ok "$BIN already on PATH" ;;
  *) warn_line="add $BIN to PATH to use 'smith' from any terminal"; say "$warn_line" ;;
esac

ok "running setup (NEST_WEB=${NEST_WEB:-y})"
NEST_WEB="${NEST_WEB:-y}" bash "$DEST/setup.sh"

echo
ok "done. try: smith info"
