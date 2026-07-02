#!/usr/bin/env bash
#
# update.sh — update bdos-ai-extensions, made for non-technical users (macOS / Linux).
#
# Does three things in order and tells you what's happening at each step:
#   1. pull the latest extensions        (git pull)
#   2. re-link them into your BDOS        (install_into_bdos.py — safe to run repeatedly;
#      works both for a "symlink" install and a "--copy" install)
#   3. register the skills with BDOS      (bdos update --regenerate)
#
# How to use:
#   - open a Terminal
#   - paste the line below and press Enter (adjust the path if the repo is elsewhere):
#
#       bash ~/Github/bdos-ai-extensions/update.sh
#
# That's all you need to type. If something goes wrong, the script explains what and why.

set -euo pipefail

# The directory this script lives in = the repo directory (no matter where you run it from).
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

echo ""
echo "=== Updating bdos-ai-extensions ==="
echo "Directory: $HERE"
echo ""

# --- Step 1: pull the latest version ------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  echo "❌ 'git' not found. Install git and try again."
  exit 1
fi

echo "① Pulling the latest version (git pull)…"
if git pull --ff-only; then
  echo "   ✔ Done."
else
  echo ""
  echo "❌ 'git pull' failed — you most likely have local changes to the files."
  echo "   Ask a technical person or the BDOS assistant for help (the message above says why)."
  exit 1
fi
echo ""

# --- Step 2: link the extensions into BDOS ------------------------------------
# Pick a Python interpreter: prefer 'python3', then 'python'.
PY=""
for cand in python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done

if [ -z "$PY" ]; then
  echo "❌ No Python found (python3/python). Install Python 3.12+ and try again."
  exit 1
fi

echo "② Linking the extensions into BDOS (install_into_bdos.py)…"
if "$PY" "$HERE/install_into_bdos.py"; then
  echo "   ✔ Done."
else
  echo ""
  echo "❌ Could not link the extensions — usually this means the script did not find your"
  echo "   BDOS-AI directory (a folder that contains both 'bdos/' and 'my/')."
  echo "   Run it again pointing at the path explicitly, e.g.:"
  echo "     $PY \"$HERE/install_into_bdos.py\" --bdos /path/to/BDOS-AI"
  exit 1
fi
echo ""

# --- Step 3: register the skills with BDOS ------------------------------------
echo "③ Registering the skills with BDOS (bdos update --regenerate)…"
if command -v bdos >/dev/null 2>&1; then
  if bdos update --regenerate; then
    echo "   ✔ Done."
  else
    echo "   ⚠ 'bdos update --regenerate' returned an error — run it manually in a BDOS session."
  fi
else
  echo "   ⚠ 'bdos' command not found in this terminal."
  echo "     That's fine if you start BDOS a different way. Finish the last step manually:"
  echo "         bdos update --regenerate"
fi

echo ""
echo "✅ Update complete. You can go back to working in BDOS."
echo ""
