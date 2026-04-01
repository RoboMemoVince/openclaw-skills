#!/usr/bin/env bash
# claude-code-run.sh — Run Claude Code on Alice (non-interactive mode)
# Usage: ./claude-code-run.sh [OPTIONS] "PROMPT"
#
# Options:
#   -d, --dir DIR       Working directory on Alice (default: /data0/Musk)
#   -m, --model MODEL   Model to use: sonnet|opus (default: sonnet)
#   -b, --budget USD    Max budget in USD (default: 1.0)
#   -f, --format FMT    Output format: json|text (default: json)
#   -h, --help          Show this help

set -euo pipefail

# Defaults
WORKDIR="/data0/Musk"
MODEL="opus"
BUDGET="2.0"
FORMAT="json"
SSH_KEY="${HOME}/.ssh/KeyPair-d9c2.pem"
ALICE="root@1.95.7.166"
CONTAINER="triton-ascend-hcq"

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--dir)    WORKDIR="$2"; shift 2 ;;
    -m|--model)  MODEL="$2"; shift 2 ;;
    -b|--budget) BUDGET="$2"; shift 2 ;;
    -f|--format) FORMAT="$2"; shift 2 ;;
    -h|--help)
      head -8 "$0" | tail -7
      exit 0
      ;;
    *)
      PROMPT="$1"; shift
      ;;
  esac
done

if [[ -z "${PROMPT:-}" ]]; then
  echo "Error: No prompt provided" >&2
  exit 1
fi

# Ensure SSH key
if [[ ! -f "$SSH_KEY" ]]; then
  cp "/root/.openclaw/workspace/.ssh/KeyPair-d9c2.pem" "$SSH_KEY" 2>/dev/null || true
  chmod 600 "$SSH_KEY"
fi

# Escape single quotes in prompt for bash -c
ESCAPED_PROMPT="${PROMPT//\'/\'\\\'\'}"

# Execute
ssh -i "$SSH_KEY" \
  -o StrictHostKeyChecking=no \
  -o ConnectTimeout=10 \
  "$ALICE" \
  "docker exec $CONTAINER bash -c 'cd $WORKDIR && claude -p \
    --permission-mode dontAsk \
    --model $MODEL \
    --max-budget-usd $BUDGET \
    --output-format $FORMAT \
    \"$ESCAPED_PROMPT\"'"
