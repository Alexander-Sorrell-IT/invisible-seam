#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# INVISIBLE SEAM — One-command demo recorder
#
# Usage:  bash record_demo.sh
#
# What it does:
#   1. Opens a fullscreen xterm running the split-screen demo
#   2. Starts ffmpeg recording the screen to demo.mp4
#   3. Waits for the demo to finish
#   4. Stops recording automatically
#   5. Prints the output file path
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT="${SCRIPT_DIR}/demo.mp4"
DISPLAY="${DISPLAY:-:0}"
LOG="${SCRIPT_DIR}/.demo_record.log"

# ── screen geometry ───────────────────────────────────────────────────────────
GEOMETRY=$(xrandr 2>/dev/null \
  | grep ' connected primary' \
  | grep -oP '\d+x\d+' \
  | head -1)

if [[ -z "$GEOMETRY" ]]; then
  GEOMETRY=$(xrandr 2>/dev/null \
    | grep ' connected' \
    | grep -oP '\d+x\d+' \
    | head -1)
fi

if [[ -z "$GEOMETRY" ]]; then
  GEOMETRY="1600x900"
fi

WIDTH="${GEOMETRY%x*}"
HEIGHT="${GEOMETRY#*x}"

echo "──────────────────────────────────────────────"
echo "  INVISIBLE SEAM — Demo Recorder"
echo "  Screen: ${WIDTH}x${HEIGHT}  Display: ${DISPLAY}"
echo "  Output: ${OUTPUT}"
echo "──────────────────────────────────────────────"
echo ""
echo "  Starting in 2 seconds..."
sleep 2

# ── sentinel file: demo writes this when done ─────────────────────────────────
DONE_SENTINEL="${SCRIPT_DIR}/.demo_done"
rm -f "$DONE_SENTINEL"

# ── launch fullscreen xterm with the demo ────────────────────────────────────
# -fa: font family  -fs: font size  -bg: background  -fg: foreground
# +sb: no scrollbar  -fullscreen: fullscreen
# On exit the demo writes the sentinel then the xterm closes
xterm \
  -fa "Monospace" \
  -fs 14 \
  -bg "#0d1117" \
  -fg "#c9d1d9" \
  +sb \
  -title "INVISIBLE SEAM" \
  -geometry "${WIDTH}x${HEIGHT}+0+0" \
  -e bash -c "
    cd '${SCRIPT_DIR}'
    python3 demo_runner.py
    touch '${DONE_SENTINEL}'
  " &

XTERM_PID=$!

# give xterm a moment to open and render
sleep 1.5

# ── start ffmpeg screen recording ────────────────────────────────────────────
ffmpeg \
  -y \
  -f x11grab \
  -video_size "${WIDTH}x${HEIGHT}" \
  -framerate 30 \
  -i "${DISPLAY}+0,0" \
  -vf "scale=1920:1080:flags=lanczos,format=yuv420p" \
  -c:v libx264 \
  -preset fast \
  -crf 18 \
  -movflags +faststart \
  "${OUTPUT}" \
  > "$LOG" 2>&1 &

FFMPEG_PID=$!
echo "  Recording started (ffmpeg pid: ${FFMPEG_PID})"
echo "  Waiting for demo to complete..."
echo ""

# ── wait for demo to finish ───────────────────────────────────────────────────
WAITED=0
MAX_WAIT=240  # 4 minutes max

while [[ ! -f "$DONE_SENTINEL" ]]; do
  sleep 1
  WAITED=$((WAITED + 1))
  if [[ $WAITED -ge $MAX_WAIT ]]; then
    echo "  Warning: demo did not finish within ${MAX_WAIT}s. Stopping anyway."
    break
  fi
done

# give ffmpeg 2 more seconds to capture the final frame
sleep 2

# ── stop recording ────────────────────────────────────────────────────────────
kill "$FFMPEG_PID" 2>/dev/null || true
wait "$FFMPEG_PID" 2>/dev/null || true

# stop xterm if still running
kill "$XTERM_PID" 2>/dev/null || true

# clean up sentinel
rm -f "$DONE_SENTINEL"

echo ""
echo "──────────────────────────────────────────────"
echo "  Recording complete."
echo "  Output: ${OUTPUT}"

if [[ -f "$OUTPUT" ]]; then
  SIZE=$(du -sh "$OUTPUT" | cut -f1)
  DURATION=$(ffprobe -v quiet -show_entries format=duration \
    -of default=noprint_wrappers=1:nokey=1 "$OUTPUT" 2>/dev/null \
    | xargs printf "%.0f" 2>/dev/null || echo "unknown")
  echo "  Size:   ${SIZE}"
  echo "  Length: ~${DURATION}s"
fi

echo "──────────────────────────────────────────────"
