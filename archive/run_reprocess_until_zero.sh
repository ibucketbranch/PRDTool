#!/bin/bash

set -euo pipefail

ROOT_DIR="/Users/michaelvalderrama/Websites/TheConversation"
cd "$ROOT_DIR"

: "${BATCH_SIZE:=200}"
: "${LLM_PROVIDER:=gemini}"

if [[ -z "${GEMINI_API_KEY:-}" || -z "${SUPABASE_SERVICE_ROLE_KEY:-}" ]]; then
  echo "GEMINI_API_KEY and SUPABASE_SERVICE_ROLE_KEY must be exported before running this script."
  exit 1
fi

if [[ ! -d "venv" ]]; then
  echo "Python virtualenv (venv) not found. Please set it up first."
  exit 1
fi

source venv/bin/activate

run_batch() {
  python3 -u reprocess_low_confidence.py --limit "$BATCH_SIZE" --llm "$LLM_PROVIDER"
}

remaining_low_conf() {
  python3 reprocess_low_confidence.py --dry-run --limit 1 --llm "$LLM_PROVIDER" \
    | sed -n 's/^Found \\([0-9]*\\) .*/\\1/p' | head -n1
}

while true; do
  run_batch
  remaining="$(remaining_low_conf)"
  remaining="${remaining:-0}"
  printf '%s | Remaining low-confidence docs: %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$remaining"
  if [[ "$remaining" -eq 0 ]]; then
    echo "All low-confidence documents have been reprocessed."
    break
  fi
  echo "Sleeping 5 seconds before the next batch..."
  sleep 5
done
