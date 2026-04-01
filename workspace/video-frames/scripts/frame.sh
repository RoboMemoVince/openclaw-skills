#!/usr/bin/env bash
set -euo pipefail

# Use FFMPEG env var if set, otherwise find in PATH
FFMPEG="${FFMPEG:-$(command -v ffmpeg 2>/dev/null || echo ffmpeg)}"

usage() {
  cat >&2 <<'EOF'
Usage:
  frame.sh <video-file> [--time HH:MM:SS] [--index N] --out /path/to/frame.jpg
  frame.sh <video-file> --scene-detect [--threshold N] --outdir /path/to/dir/

Options:
  --time HH:MM:SS     Extract frame at timestamp
  --index N           Extract Nth frame (0-indexed)
  --scene-detect      Detect scene changes (PPT slide transitions etc.)
  --threshold N       Scene detection threshold (default: 3.0, lower=more sensitive)
  --outdir DIR        Output directory for scene-detect frames
  --out FILE          Output file for single frame

Examples:
  frame.sh video.mp4 --out /tmp/frame.jpg
  frame.sh video.mp4 --time 00:00:10 --out /tmp/frame-10s.jpg
  frame.sh video.mp4 --scene-detect --outdir /tmp/scenes/
  frame.sh video.mp4 --scene-detect --threshold 5.0 --outdir /tmp/scenes/
EOF
  exit 2
}

if [[ "${1:-}" == "" || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
fi

in="${1:-}"
shift || true

time=""
index=""
out=""
scene_detect=false
threshold="3.0"
outdir=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --time)
      time="${2:-}"
      shift 2
      ;;
    --index)
      index="${2:-}"
      shift 2
      ;;
    --out)
      out="${2:-}"
      shift 2
      ;;
    --scene-detect)
      scene_detect=true
      shift
      ;;
    --threshold)
      threshold="${2:-3.0}"
      shift 2
      ;;
    --outdir)
      outdir="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      ;;
  esac
done

if [[ ! -f "$in" ]]; then
  echo "File not found: $in" >&2
  exit 1
fi

# --- Scene Detection Mode ---
if [[ "$scene_detect" == true ]]; then
  if [[ "$outdir" == "" ]]; then
    echo "Missing --outdir for scene-detect mode" >&2
    usage
  fi
  mkdir -p "$outdir"

  echo "Detecting scene changes (threshold=$threshold)..." >&2

  # Step 1: detect scene change timestamps via scdet
  # Note: ffmpeg outputs both "lavfi.scd.time" (scene detection time) and "time" (frame processing time)
  # We must match "lavfi.scd.time" specifically to get the correct scene detection timestamps
  timestamps=$($FFMPEG -hide_banner -i "$in" \
    -vf "scdet=t=${threshold}:sc_pass=1" \
    -f null - 2>&1 \
    | grep "lavfi.scd.score" \
    | sed -E 's/.*lavfi\.scd\.score: ([0-9.]+).*lavfi\.scd\.time: ([0-9.]+).*/\2 \1/')

  if [[ -z "$timestamps" ]]; then
    echo "No scene changes detected at threshold=$threshold" >&2
    exit 0
  fi

  count=0
  # Step 2: extract frame at each detected timestamp
  while IFS=' ' read -r ts score; do
    count=$((count + 1))
    # Convert seconds to HH:MM:SS for display
    # Use 10# to avoid octal interpretation of zero-padded numbers
    ts_int=$((10#${ts%.*}))
    h=$(printf "%02d" $((ts_int / 3600)))
    m=$(printf "%02d" $(((ts_int % 3600) / 60)))
    s=$(printf "%02d" $((ts_int % 60)))
    ts_fmt="${h}:${m}:${s}"

    fname=$(printf "scene_%03d_%s_s%.1f.jpg" "$count" "$ts_fmt" "$score")
    $FFMPEG -hide_banner -loglevel error -y \
      -ss "$ts" -i "$in" \
      -frames:v 1 -q:v 2 \
      "${outdir}/${fname}"
    echo "${outdir}/${fname}  (${ts_fmt}, score=${score})"
  done <<< "$timestamps"

  echo "Extracted $count scene-change frames to $outdir" >&2
  exit 0
fi

# --- Single Frame Mode ---
if [[ "$out" == "" ]]; then
  echo "Missing --out" >&2
  usage
fi

mkdir -p "$(dirname "$out")"

if [[ "$index" != "" ]]; then
  $FFMPEG -hide_banner -loglevel error -y \
    -i "$in" \
    -vf "select=eq(n\\,${index})" \
    -vframes 1 \
    "$out"
elif [[ "$time" != "" ]]; then
  $FFMPEG -hide_banner -loglevel error -y \
    -ss "$time" \
    -i "$in" \
    -frames:v 1 \
    "$out"
else
  $FFMPEG -hide_banner -loglevel error -y \
    -i "$in" \
    -vf "select=eq(n\\,0)" \
    -vframes 1 \
    "$out"
fi

echo "$out"
