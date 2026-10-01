#!/bin/zsh
# Double-click in Finder to start Object Intelligence. It builds the browser part when its sources changed, starts the
# server and opens http://127.0.0.1:8766. Close this Terminal window (or press Ctrl+C) to stop it.

cd "$(dirname "$0")" || exit 1
export PATH="$PATH:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin" # Finder starts without your shell's PATH
port="${OI_PORT:-8766}"

wait_for_key() {
  read -sk1 "?$1 Eine Taste schließt das Fenster."
  exit 1
}

if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Object Intelligence läuft schon, ich öffne nur den Browser."
  open "http://127.0.0.1:$port"
  exit 0
fi
command -v uv >/dev/null || wait_for_key "uv fehlt: bitte von https://docs.astral.sh/uv/ installieren."
sources="$(find web/src web/index.html web/package.json -type f -newer web/dist/index.html -print -quit 2>/dev/null)"
if [[ ! -f web/dist/index.html || -n "$sources" ]]; then
  command -v npm >/dev/null || wait_for_key "Node.js fehlt: bitte von https://nodejs.org installieren."
  echo "Baue die Oberfläche …"
  [[ -d web/node_modules ]] || npm --prefix web install
  npm --prefix web run build || { npm --prefix web install && npm --prefix web run build; } \
    || wait_for_key "Der Build ist fehlgeschlagen."  # a failed build may only lack a new dependency
fi
exec uv run python -m oi
