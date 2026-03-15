#!/usr/bin/env bash
# run-k6-test.sh — Start target app, run k6 test, clean up.
# Usage: ./scripts/run-k6-test.sh <k6-script-path> <app-type> [base-url]
#
# Arguments:
#   k6-script-path   Path to the k6 test script (e.g., k6/kassandra/mr-15-statement.js)
#   app-type         "calliope" or "midas"
#   base-url         Optional, defaults based on app-type
#
# This script is designed to be called by Kassandra via run_command.
# It handles app startup, health check, k6 execution, and cleanup
# in a single process — preventing run_command from hanging.

set -euo pipefail

SCRIPT_PATH="${1:?Usage: run-k6-test.sh <script-path> <app-type> [base-url] [branch]}"
APP_TYPE="${2:?Usage: run-k6-test.sh <script-path> <app-type> [base-url] [branch]}"
BASE_URL="${3:-}"
BRANCH="${4:-}"

# ── Step 0: Checkout MR source branch if specified ──
if [ -n "$BRANCH" ]; then
  echo "Checking out branch: $BRANCH"
  git fetch origin "$BRANCH" 2>/dev/null || git fetch 2>/dev/null || true
  git checkout "$BRANCH" 2>/dev/null || git checkout "origin/$BRANCH" 2>/dev/null || echo "WARNING: Could not checkout $BRANCH"
fi

APP_PID=""

cleanup() {
  if [ -n "$APP_PID" ]; then
    echo ""
    echo "Cleaning up: killing app (PID $APP_PID)..."
    kill "$APP_PID" 2>/dev/null || true
    wait "$APP_PID" 2>/dev/null || true
    echo "App stopped."
  fi
}
trap cleanup EXIT

# ── Step 1: Start the target application ──
case "$APP_TYPE" in
  calliope)
    BASE_URL="${BASE_URL:-http://localhost:3000}"
    HEALTH_URL="$BASE_URL/api/health"
    LOG_FILE="/tmp/calliope.log"
    echo "Starting Calliope Books..."
    cd demos/calliope-books
    npm install --silent 2>/dev/null || true
    node app.js > "$LOG_FILE" 2>&1 &
    APP_PID=$!
    cd ../..
    ;;
  midas)
    BASE_URL="${BASE_URL:-http://localhost:8000}"
    HEALTH_URL="$BASE_URL/api/health"
    LOG_FILE="/tmp/midas.log"
    echo "Starting Midas Bank..."
    cd demos/midas-bank
    pip3 install --break-system-packages -r requirements.txt --quiet 2>/dev/null || pip install --break-system-packages -r requirements.txt --quiet 2>/dev/null || python3 -m pip install --break-system-packages -r requirements.txt --quiet 2>/dev/null || echo "WARNING: pip install failed"
    python3 -c "import fastapi; print(f'FastAPI {fastapi.__version__}')" 2>/dev/null || { echo "FATAL: FastAPI not installed"; exit 1; }
    python3 -m uvicorn app:app --host 0.0.0.0 --port 8000 > "$LOG_FILE" 2>&1 &
    APP_PID=$!
    cd ../..
    ;;
  *)
    echo "ERROR: Unknown app type '$APP_TYPE'. Use 'calliope' or 'midas'."
    exit 1
    ;;
esac

# ── Step 2: Wait for health check ──
echo "Waiting for app to start..."
for i in $(seq 1 10); do
  if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
    echo "App is healthy (attempt $i)."
    break
  fi
  if [ "$i" -eq 10 ]; then
    echo "ERROR: App failed to start after 10 attempts."
    echo "--- App log ---"
    cat "$LOG_FILE" 2>/dev/null || echo "(no log)"
    exit 1
  fi
  sleep 1
done

# ── Step 3: Validate k6 script ──
echo ""
echo "Validating k6 script: $SCRIPT_PATH"
if ! k6 inspect "$SCRIPT_PATH" > /dev/null 2>&1; then
  echo "ERROR: k6 script has syntax errors:"
  k6 inspect "$SCRIPT_PATH" 2>&1 || true
  exit 1
fi
echo "Script validated OK."

# ── Step 4: Create results directory ──
mkdir -p k6/kassandra/results

# ── Step 5: Run k6 test ──
echo ""
echo "════════════════════════════════════════════════════════"
echo "  Running k6: $SCRIPT_PATH"
echo "════════════════════════════════════════════════════════"
echo ""

k6 run --env BASE_URL="$BASE_URL" "$SCRIPT_PATH" 2>&1
K6_EXIT=$?

echo ""
if [ $K6_EXIT -eq 0 ]; then
  echo "k6 completed successfully (exit code 0)."
else
  echo "k6 exited with code $K6_EXIT (threshold breach or error)."
fi

# ── Step 6: Show results ──
echo ""
echo "Result files:"
ls -la k6/kassandra/results/ 2>/dev/null || echo "(no result files)"

# cleanup via trap
exit $K6_EXIT
