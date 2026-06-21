#!/usr/bin/env bash
# contract-ci.sh — Self-contained contract verification for CI and sdd-verify.
# Builds the app, starts the server, runs the full contract suite, and cleans up.
# Usage: bash test/contract-ci.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-3000}"
SERVER_LOG=$(mktemp /tmp/next-server-XXXX.log)
EXIT_CODE=0

cleanup() {
  if [ -n "${SERVER_PID:-}" ]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -f "$SERVER_LOG"
}

trap cleanup EXIT INT TERM

echo "==> Building application..."
cd "$ROOT_DIR"
pnpm exec next build >&2

echo "==> Starting server on port $PORT..."
pnpm exec next start -p "$PORT" >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

# Wait for the server to be ready (up to 30s)
echo "==> Waiting for server..."
for i in $(seq 1 30); do
  if curl -s -o /dev/null -w '%{http_code}' "http://localhost:$PORT" 2>/dev/null | grep -q '200'; then
    echo "==> Server ready after ${i}s"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "==> ERROR: Server did not start within 30s"
    cat "$SERVER_LOG"
    exit 1
  fi
  sleep 1
done

echo "==> Running contract verification..."
CONTRACT_VERIFY_ALL=1 node "$ROOT_DIR/test/contract-verify.cjs" || EXIT_CODE=$?

echo "==> Done (exit code: $EXIT_CODE)"
exit "$EXIT_CODE"
