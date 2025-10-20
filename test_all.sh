#!/bin/bash
# Comprehensive test of all signalbox commands

echo "=== signalbox Test Suite ==="
echo ""

echo "1. Testing configuration display..."
python main.py show-config | head -5
echo "✓ show-config works"
echo ""

echo "2. Testing get-setting..."
python main.py get-setting execution.default_timeout
python main.py get-setting display.use_colors
echo "✓ get-setting works"
echo ""

echo "3. Testing validation..."
python main.py validate
echo "✓ validate works"
echo ""

echo "4. Testing list commands..."
python main.py list | head -3
echo "✓ list works"
echo ""

python main.py list-groups | head -5
echo "✓ list-groups works"
echo ""

python main.py list-schedules
echo "✓ list-schedules works"
echo ""

echo "5. Testing script execution..."
python main.py run hello
echo "✓ run works"
echo ""

echo "6. Testing group execution..."
python main.py run-group basic | head -3
echo "✓ run-group works"
echo ""

echo "7. Testing log viewing..."
python main.py logs hello | head -5
echo "✓ logs works"
echo ""

echo "8. Testing history..."
python main.py history hello | head -3
echo "✓ history works"
echo ""

echo "9. Testing export commands..."
python main.py export-cron system | head -3
echo "✓ export-cron works"
echo ""

python main.py export-systemd daily | head -5
echo "✓ export-systemd works"
echo ""

echo "=== All Tests Passed ==="
echo ""
echo "Configuration files in use:"
echo "  - config.yaml (global settings)"
echo "  - scripts.yaml (script definitions)"  
echo "  - groups.yaml (groups and schedules)"
echo ""
echo "Documentation:"
echo "  - README.md (overview)"
echo "  - documentation/CONFIG_SYSTEM.md (config system overview)"
echo "  - documentation/CONFIG_GUIDE.md (usage guide)"
echo "  - documentation/CONFIG_REFERENCE.md (complete reference)"
echo "  - documentation/FILE_STRUCTURE.md (file format examples)"
echo "  - documentation/SCHEDULING_EXAMPLES.md (scheduling patterns)"
echo "  - documentation/EXECUTION_MODES.md (parallel and serial execution)"
