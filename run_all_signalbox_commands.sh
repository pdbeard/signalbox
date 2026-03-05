#!/bin/sh
# Run all main signalbox CLI commands for testing/demo

python3 signalbox.py --help
python3 signalbox.py task --help
python3 signalbox.py group --help
python3 signalbox.py log --help
python3 signalbox.py config --help
python3 signalbox.py runtime --help
python3 signalbox.py alerts
python3 signalbox.py export-cron --help
python3 signalbox.py export-systemd --help
python3 signalbox.py init --help
python3 signalbox.py list-schedules
python3 signalbox.py notify-test
python3 signalbox.py run --help
python3 signalbox.py list --help
python3 signalbox.py validate --help

# Task commands
python3 signalbox.py task list
python3 signalbox.py task run --help
python3 signalbox.py task run check_system_load           # run with inline output preview
python3 signalbox.py task run check_system_load --quiet   # suppress output preview
python3 signalbox.py task run --all

# Group commands
python3 signalbox.py group list
python3 signalbox.py group run test_serial_fail           # stops after fail_test fails
python3 signalbox.py group run test_serial_continue       # continues after fail_test fails

# Log commands
python3 signalbox.py log list                             # table with output preview column
python3 signalbox.py log list --help
python3 signalbox.py log list --verbose                   # expanded output per entry
python3 signalbox.py log list --today
python3 signalbox.py log list --failed
python3 signalbox.py log list --last 10
python3 signalbox.py log show check_system_load
python3 signalbox.py log history check_system_load

# Config commands
python3 signalbox.py config show
python3 signalbox.py config validate
