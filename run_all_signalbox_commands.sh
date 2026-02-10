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
python3 signalbox.py task list
python3 signalbox.py task run --all
python3 signalbox.py group list
python3 signalbox.py group run basic
python3 signalbox.py log list
python3 signalbox.py config show
python3 signalbox.py config validate
