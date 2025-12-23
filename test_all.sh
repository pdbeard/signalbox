#!/bin/bash
# Comprehensive test of all signalbox commands

# Find Python executable
if [ -f "venv/bin/python" ]; then
    PYTHON="venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
else
    echo "❌ Error: No Python executable found"
    exit 1
fi

# Track test results
FAILED_TESTS=0
PASSED_TESTS=0

# Helper function to run test and check result
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
        cat /tmp/signalbox_test_output | head -10
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
    echo ""
}

echo "=== signalbox Test Suite ==="
echo "Using Python: $PYTHON"
echo ""

echo "1. Configuration Commands"
run_test "show-config" "$PYTHON signalbox.py show-config"
run_test "get-setting" "$PYTHON signalbox.py get-setting execution.default_timeout"

echo "2. Validation"
run_test "validate" "$PYTHON signalbox.py validate"

echo "3. List Commands"
run_test "list scripts" "$PYTHON signalbox.py list"
run_test "list-groups" "$PYTHON signalbox.py list-groups"
run_test "list-schedules" "$PYTHON signalbox.py list-schedules"

echo "4. Script Execution"
run_test "run script" "$PYTHON signalbox.py run hello"

echo "5. Group Execution"
run_test "run-group" "$PYTHON signalbox.py run-group basic"

echo "6. Log Commands"
run_test "logs (view latest)" "$PYTHON signalbox.py logs hello"
run_test "history" "$PYTHON signalbox.py history hello"

echo "7. Export Commands"
run_test "export-cron" "$PYTHON signalbox.py export-cron system"
run_test "export-systemd" "$PYTHON signalbox.py export-systemd system"

# Summary
echo "========================================="
if [ $FAILED_TESTS -eq 0 ]; then
    echo "✓ All Tests Passed ($PASSED_TESTS/$PASSED_TESTS)"
    EXIT_CODE=0
else
    echo "❌ Some Tests Failed"
    echo "   Passed: $PASSED_TESTS"
    echo "   Failed: $FAILED_TESTS"
    EXIT_CODE=1
fi
echo ""
echo "Configuration files found:"
[ -f "config/signalbox.yaml" ] && echo "  ✓ config/signalbox.yaml (global settings)" || echo "  ✗ config/signalbox.yaml (missing)"
[ -d "config/scripts" ] && echo "  ✓ config/scripts/ ($(find config/scripts -name '*.yaml' -o -name '*.yml' 2>/dev/null | wc -l | xargs) files)" || echo "  ✗ config/scripts (missing)"
[ -d "config/groups" ] && echo "  ✓ config/groups/ ($(find config/groups -name '*.yaml' -o -name '*.yml' 2>/dev/null | wc -l | xargs) files)" || echo "  ✗ config/groups (missing)"

exit $EXIT_CODE
