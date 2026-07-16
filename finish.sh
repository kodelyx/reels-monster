#!/usr/bin/env bash
# Finish the pipeline: render (10) → trim (11) → output/final_trimmed.mp4
#
# Everything upstream (avatar 5/5, broll 10/10, caption+popups, music) is ready.
# This just runs the two Chrome/Remotion stages that must run on a real terminal
# (a sandboxed shell can't launch Chrome — macOS blocks its Mach ports).
#
# If you have real Gemini music, run stage 09 first (needs the native gemini
# server up + Chrome extension cookies synced):
#   cd ../free-gemini-api && ./start-native.sh      # in another tab
#   python3 orchestrator.py --from 09_music
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# Point Remotion at an already-installed Chrome so it never downloads one.
# Adjust if yours lives elsewhere (`find / -name chrome-headless-shell 2>/dev/null`).
if [[ -z "${REMOTION_CHROME:-}" ]]; then
  for c in \
    "$HOME/Library/Caches/ms-playwright/chromium_headless_shell-1228/chrome-headless-shell-mac-arm64/chrome-headless-shell" \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; do
    [[ -x "$c" ]] && export REMOTION_CHROME="$c" && break
  done
fi
echo "🌐 Chrome: ${REMOTION_CHROME:-<remotion will auto-download>}"

python3 orchestrator.py --resume
echo "✅ Done → $(pwd)/output/"
ls -la output/*.mp4
