#!/bin/sh
# Run all main signalbox CLI commands for testing/demo

python3 -m signalbox --help
python3 -m signalbox task --help
python3 -m signalbox group --help
python3 -m signalbox log --help
python3 -m signalbox config --help
python3 -m signalbox alerts
python3 -m signalbox export-cron --help
python3 -m signalbox export-systemd --help
python3 -m signalbox init --help
python3 -m signalbox list-schedules
python3 -m signalbox notify-test
python3 -m signalbox run --help
python3 -m signalbox list --help
python3 -m signalbox validate --help

# Task commands
python3 -m signalbox task list
python3 -m signalbox task run --help
python3 -m signalbox task run check_system_load           # run with inline output preview
python3 -m signalbox task run check_system_load --quiet   # suppress output preview
python3 -m signalbox task run --all

# Group commands
python3 -m signalbox group list
python3 -m signalbox group run test_serial_fail           # stops after fail_test fails
python3 -m signalbox group run test_serial_continue       # continues after fail_test fails

# Log commands
python3 -m signalbox log list                             # table with output preview column
python3 -m signalbox log list --help
python3 -m signalbox log list --verbose                   # expanded output per entry
python3 -m signalbox log list --today
python3 -m signalbox log list --failed
python3 -m signalbox log list --last 10
python3 -m signalbox log show check_system_load
python3 -m signalbox log history check_system_load

# Config commands
python3 -m signalbox config show
python3 -m signalbox config validate
