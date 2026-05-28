# Signalbox CLI Expansion Ideas

## Log and History Management
- `logs <name> <timestamp>`: Show a specific historical log by timestamp or filename
- `logs --all`: Show the latest log for all scripts (summary view)
- `log-history --all`: List all logs for all scripts, optionally grouped by script
- `logs --search <pattern>`: Search within logs for a string or regex
- `logs --tail <name> [N]`: Tail the last N lines of the latest log (like `tail -n`)
- `logs --follow <name>`: Stream log output in real time (like `tail -f`), if logs are being written live
- `logs --summary <name>`: Show a summary (counts by severity, errors, etc.) for a script’s logs
- `logs --clear <name>`: Clear all logs for a specific script
- `logs --clear-all`: Clear all logs for all scripts

## Alert and Notification Management
- `alerts --clear`: Clear all or specific alerts
- `alerts --filter <severity|script>`: Filter alerts by severity or script
- `alerts --watch`: Watch for new alerts in real time

## Script and Group Management
- `add-script`, `remove-script`, `edit-script`: Manage scripts directly from the CLI
- `add-group`, `remove-group`, `edit-group`: Manage groups from the CLI
- `describe <name>`: Show full details (YAML/config) for a script or group

## Execution Enhancements
- `run --dry-run <name>`: Show what would be executed, without running
- `run --env <VAR=VAL>`: Override environment variables for a run
- `run-group --parallel/--serial`: Override group execution mode on the fly

## Scheduling and Automation
- `schedule <group> <cron>`: Add or update a scheduled run from the CLI
- `unschedule <group>`: Remove a scheduled run

## Configuration and Validation
- `validate --all`: Validate all config, scripts, and groups
- `validate --fix`: Attempt to auto-fix common config issues

## User Experience and Advanced
- `help <command>`: Show detailed help for a specific command
- `version`: Show current version and environment info
- `completion`: Output shell completion script for bash/zsh/fish
- `export <format>`: Export config/scripts/groups in different formats (YAML, JSON, etc.)
- `import <file>`: Import scripts/groups from a file


