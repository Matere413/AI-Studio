#!/usr/bin/env bash
# ─── Unit Test Runner ──────────────────────────────────────────
# Runs all Phase 1 unit tests using Node's built-in test runner
# with experimental TypeScript stripping.
#
# Usage:
#   bash test/unit-tests.sh           # run all unit tests
#   bash test/unit-tests.sh --watch   # watch mode (requires nodemon or similar)

set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "==> Running unit tests (node --experimental-strip-types --test)..."
echo ""

# Guard: fail if any test file contains focused tests (it.only / describe.only / test.only)
FOCUSED=$(find src \( -name '*.test.ts' -o -name '*.test.tsx' \) -type f -exec grep -ln '\(it\.only\|describe\.only\|test\.only\)' {} + || true)
if [ -n "$FOCUSED" ]; then
  echo "ERROR: Focused tests found — remove it.only / describe.only from:"
  echo "$FOCUSED"
  exit 1
fi

# Build file list using an array to preserve bracket characters in paths
declare -a TEST_FILES=()
while IFS= read -r -d '' file; do
  echo "── ${file}"
  TEST_FILES+=("$file")
done < <(find src \( -name '*.test.ts' -o -name '*.test.tsx' \) -type f -print0 | sort -z)
echo ""

NODE_OPTIONS="--experimental-strip-types" node --test "${TEST_FILES[@]}"
