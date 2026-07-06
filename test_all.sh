#!/bin/bash
# Full test run: unit tests via pytest, then a CLI smoke test against a
# throwaway config home so nothing touches your real ~/.config/signalbox.

set -u

# Find Python executable
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
else
    echo "❌ Error: No Python executable found"
    exit 1
fi

echo "=== signalbox Test Suite ==="
echo "Using Python: $PYTHON"
echo ""

echo "1. Unit tests (pytest)"
if ! "$PYTHON" -m pytest -q; then
    echo "❌ Unit tests failed"
    exit 1
fi
echo ""

# CLI smoke test in an isolated config home seeded from the packaged defaults
SMOKE_HOME="$(mktemp -d)"
trap 'rm -rf "$SMOKE_HOME"' EXIT
mkdir -p "$SMOKE_HOME/config" "$SMOKE_HOME/logs" "$SMOKE_HOME/runtime/tasks" "$SMOKE_HOME/runtime/groups"
cp -R signalbox/config/. "$SMOKE_HOME/config/"
export SIGNALBOX_HOME="$SMOKE_HOME"

FAILED_TESTS=0
PASSED_TESTS=0

run_test() {
    local test_name="$1"
    local command="$2"

    echo "Testing: $test_name"
    if eval "$command" > /tmp/signalbox_test_output 2>&1; then
        echo "✓ $test_name passed"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo "❌ $test_name FAILED"
        echo "   Output:"
        head -10 /tmp/signalbox_test_output
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    echo ""
}

echo "2. CLI smoke test (SIGNALBOX_HOME=$SMOKE_HOME)"
run_test "config show" "$PYTHON -m signalbox config show"
run_test "config show KEY" "$PYTHON -m signalbox config show execution.default_timeout"
run_test "validate" "$PYTHON -m signalbox validate"
run_test "task list" "$PYTHON -m signalbox task list"
run_test "group list" "$PYTHON -m signalbox group list"
run_test "list-schedules" "$PYTHON -m signalbox list-schedules"
run_test "run task" "$PYTHON -m signalbox run hello"
run_test "group run" "$PYTHON -m signalbox group run example"
run_test "log show" "$PYTHON -m signalbox log show hello"
run_test "log history" "$PYTHON -m signalbox log history hello"
run_test "log list" "$PYTHON -m signalbox log list"

echo "========================================="
if [ $FAILED_TESTS -eq 0 ]; then
    echo "✓ All CLI smoke tests passed ($PASSED_TESTS/$PASSED_TESTS)"
    exit 0
else
    echo "❌ Some CLI smoke tests failed"
    echo "   Passed: $PASSED_TESTS"
    echo "   Failed: $FAILED_TESTS"
    exit 1
fi
