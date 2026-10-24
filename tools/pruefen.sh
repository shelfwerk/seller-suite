#!/usr/bin/env bash
# Checks before every push: plugin validation, private data, Python syntax.
#   bash tools/pruefen.sh
set -u
cd "$(dirname "$0")/.."
fehler=0

echo "== claude plugin validate --strict (Marktplatz + Plugins)"
if command -v claude >/dev/null 2>&1; then
  claude plugin validate --strict . || fehler=1
  for p in plugins/*/; do
    claude plugin validate --strict "$p" || fehler=1
  done
else
  echo "claude CLI nicht gefunden – übersprungen"; fehler=1
fi

echo "== private Daten"
python3 tools/privat_check.py || fehler=1

echo "== Python-Syntax"
python3 - <<'PY' || fehler=1
import pathlib, sys
bad = 0
for f in pathlib.Path("plugins").rglob("*.py"):
    try:
        compile(f.read_text(encoding="utf-8"), str(f), "exec")
    except SyntaxError as e:
        print(e); bad = 1
sys.exit(bad)
PY

echo "== Netzwerkzugriffe in den Skripten (nur ListingDoctor darf)"
treffer=$(grep -rlE "urllib\.request|http\.client|requests\.|socket\.|urlopen" plugins --include=*.py | grep -v "plugins/listingdoctor/" || true)
if [ -n "$treffer" ]; then echo "unerwartet: $treffer"; fehler=1; else echo "ok"; fi

if [ "$fehler" -eq 0 ]; then echo "✔ alles in Ordnung"; else echo "✘ bitte Funde beheben"; fi
exit "$fehler"
