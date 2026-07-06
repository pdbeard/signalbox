![signalbox logo](logo_ideas/event-portal-blocks.svg)

# signalbox

Signalbox is a CLI tool for managing, executing, and monitoring shell tasks with detailed logging, pattern-based alerting, scheduling exports, and group execution.

## Main Features

- List tasks and their last run status
- Run individual tasks or task groups (serial or parallel)
- Per-run logs with automatic rotation (by count or age)
- Pattern-based alerts on task output, with optional desktop notifications
- Generate systemd/cron configurations for scheduled groups
- Optional system tray app showing red/green status at a glance

## Installation

### Recommended: Global Install with pipx

Install pipx if you don't have it:

    python3 -m pip install --user pipx
    python3 -m pipx ensurepath

Then install signalbox globally from your local source:

    pipx install .

    # With the system tray app:
    pipx install ".[tray]"

This makes the `signalbox` command available globally, in an isolated environment.

### Local Development Install

If you want to develop or test signalbox locally, use a virtual environment:

    python3 -m venv venv
    source venv/bin/activate
    pip install -e ".[dev]"

When developing, you can run directly from the project directory without installing globally:

```bash
python -m signalbox list  # Uses ./config/ in the current directory if present
```

### Initialize Configuration

After installation, set up your configuration directory:

```bash
signalbox init
```

This creates `~/.config/signalbox/` with:

- Global configuration file (`config/signalbox.yaml`)
- Task definitions directory (`config/tasks/`)
- Group definitions directory (`config/groups/`)
- Pre-built example tasks and groups (`config/catalog/`)
- Log directory (`logs/`)
- Runtime state directory (`runtime/`)

You can now run `signalbox` from any directory on your system.

### Configuration Location

Signalbox looks for configuration in the following order:

1. **`$SIGNALBOX_HOME`** — custom location via environment variable (highest priority)
2. **`$XDG_CONFIG_HOME/signalbox`** — XDG Base Directory specification (if `XDG_CONFIG_HOME` is set)
3. **`~/.config/signalbox/`** — user configuration directory (created by `signalbox init`)
4. **Current directory** — for development or project-specific configurations (if `./config/signalbox.yaml` exists)

```bash
# Explicit override
export SIGNALBOX_HOME=/path/to/your/config
signalbox list

# Or point at a specific signalbox.yaml for one invocation
signalbox --config /path/to/config/signalbox.yaml list
```

## Commands

### Setup

- `signalbox init` — initialize configuration (run once after installation)

### Shortcuts

- `signalbox list` — list all tasks with status and last run time
- `signalbox run NAME` — run a task
- `signalbox validate` — validate configuration files

### Tasks

- `signalbox task list` — list all tasks, grouped by config file
- `signalbox task run NAME` — run a single task (shows an output preview; `--quiet` to suppress)
- `signalbox task run --all` — run every configured task

### Groups

- `signalbox group list` — list all groups and their tasks
- `signalbox group run NAME` — run all tasks in a group (serial or parallel)
- `signalbox list-schedules` — show scheduled groups with cron expressions

### Logs

- `signalbox log show TASK` — view the latest log for a task
- `signalbox log history TASK` — list all historical runs for a task
- `signalbox log list [--task NAME] [--failed] [--today] [--since DATE] [--last N] [-v]` — browse runs across all tasks
- `signalbox log tail TASK` — follow log output in real time
- `signalbox log clear --task NAME` / `signalbox log clear --all` — clear logs

### Configuration

- `signalbox config show [KEY]` — display all settings, or one (e.g. `config show execution.default_timeout`)
- `signalbox config path` — print the configuration directory
- `signalbox config check-permissions` — warn if config/log files are readable or writable by other users
- `signalbox config validate` — validate configuration files

### Alerts & Notifications

- `signalbox alerts [TASK] [--severity LEVEL] [--days N]` — list recent alerts
- `signalbox notify-test` — send a test desktop notification

### Scheduling Exports

- `signalbox export-systemd GROUP [--user]` — generate systemd service/timer files
- `signalbox export-cron GROUP` — generate a crontab entry

### Tray App

- `signalbox-tray` — system tray icon with status polling (requires `pip install "signalbox[tray]"`)

See [documentation/TRAY_USAGE.md](documentation/TRAY_USAGE.md) for details.

## Configuration

### Tasks (`config/tasks/`)

All `*.yaml`/`*.yml` files in the directory are loaded. Example `config/tasks/system.yaml`:

```yaml
tasks:
  - name: system_uptime
    command: uptime
    description: Show system uptime

  - name: disk_check
    command: df -h /
    description: Check root disk usage
    timeout: 30          # Optional: per-task timeout in seconds (0 = no timeout)
    log_limit:
      type: age
      value: 7           # Keep logs for 7 days
```

Each task requires:

- `name` — unique identifier
- `command` — shell command to execute
- `description` — human-readable description

Optional fields:

- `timeout` — per-task timeout in seconds; overrides `execution.default_timeout` (0 disables the timeout)
- `log_limit` — log rotation: `type: count` keeps the N most recent logs, `type: age` keeps logs for N days
- `alerts` — output pattern alerts (see Alerting below)

**Organization tips:** split files by functionality (`basic.yaml`, `backup.yaml`), by environment (`production.yaml`, `staging.yaml`), or by team.

### Groups (`config/groups/`)

Groups organize tasks into collections that run together. Example `config/groups/daily.yaml`:

```yaml
groups:
  - name: daily
    description: Daily maintenance tasks
    execution: serial        # or: parallel
    stop_on_error: true      # serial mode: stop at the first failure
    schedule: "0 2 * * *"    # optional cron expression, 2 AM daily
    tasks:
      - backup
      - cleanup
```

- `name`, `description`, `tasks` are required
- `execution` — `serial` (default) or `parallel`
- `stop_on_error` — serial mode only; stop the group when a task fails
- `schedule` — optional cron expression; only scheduled groups can be exported to systemd/cron

Only groups can be scheduled. A task that needs its own schedule can be the sole member of a group.

### Scheduling Examples

```yaml
groups:
  # Every 5 minutes
  - name: monitoring
    description: System monitoring
    schedule: "*/5 * * * *"
    tasks: [cpu_check, disk_check]

  # Daily at 2 AM
  - name: daily
    description: Daily maintenance
    schedule: "0 2 * * *"
    tasks: [backup, reports]

  # Weekly on Sunday at 3 AM
  - name: weekly
    description: Weekly audit
    schedule: "0 3 * * 0"
    tasks: [full_backup, audit]
```

## Automation Setup

Signalbox does not run its own scheduler daemon — it generates systemd or cron configuration for you to review and install. Only groups with a `schedule` field can be exported.

### Option 1: systemd

```bash
# Generate files (creates systemd/<group>/ directory)
signalbox export-systemd daily

# Install (requires root)
sudo cp systemd/daily/signalbox-daily.service systemd/daily/signalbox-daily.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now signalbox-daily.timer

# Check status
sudo systemctl status signalbox-daily.timer
```

For user-level units (no root):

```bash
signalbox export-systemd daily --user
```

### Option 2: cron

```bash
# Generate entry (creates cron/<group>/ directory)
signalbox export-cron daily

# Add to crontab
crontab -e
# Paste the generated line
```

## Alerting

Signalbox matches patterns against task output and records alerts, optionally sending desktop notifications.

### Defining Alerts in Tasks

```yaml
tasks:
  - name: disk_check
    command: ./check_disk.sh
    description: Check disk usage
    alerts:
      - pattern: "Disk usage is above 80%"
        title: "Disk Space Critical"
        message: "Disk usage is above 80%!"
        severity: critical
      - pattern: "Disk usage is above 60%"
        message: "Disk usage is above 60%"
        severity: warning
      - pattern: "Disk OK"
        message: "Disk usage is normal"
        severity: info
        notify: false        # Don't send a notification for this alert
```

**Alert fields:**

- `pattern` (required) — regex or substring to match in task output (stdout or stderr)
- `message` (required) — message to log and notify when the pattern matches
- `severity` (optional) — `info`, `warning`, or `critical` (default: `info`)
- `title` (optional) — custom notification title (default: `"Alert: {task_name}"`)
- `notify` (optional) — override the global notification setting for this alert
- `on_failure_only` (optional) — if true, only notify for warning/critical severity

### Viewing Alerts

```bash
signalbox alerts                                # all recent alerts
signalbox alerts disk_check --severity critical # filter by task and severity
```

Alerts are stored in `logs/<task_name>/alerts/alerts.jsonl` and pruned per the retention policy in `signalbox.yaml`.

See [documentation/NOTIFICATIONS.md](documentation/NOTIFICATIONS.md) for full notification configuration options.

## Validation

Before deploying schedules, validate your configuration:

```bash
signalbox validate
```

This checks for missing required fields, duplicate names, non-existent task references, invalid per-task timeouts, invalid cron syntax, and YAML errors.

## Documentation

Guides are available in the `documentation/` directory:

- **[Configuration Guide](documentation/CONFIG_GUIDE.md)** — global settings, tasks, and groups
- **[Writing Scripts Guide](documentation/WRITING_SCRIPTS.md)** — best practices for scripts that work with signalbox
- **[File Structure](documentation/FILE_STRUCTURE.md)** — project layout and multi-file organization
- **[Config System](documentation/CONFIG_SYSTEM.md)** — overview of the configuration system
- **[Execution Modes](documentation/EXECUTION_MODES.md)** — parallel vs serial execution
- **[Scheduling Examples](documentation/SCHEDULING_EXAMPLES.md)** — real-world scheduling patterns
- **[Notifications](documentation/NOTIFICATIONS.md)** — desktop notification configuration
- **[Tray Usage](documentation/TRAY_USAGE.md)** — system tray app

## Exit Codes

Signalbox follows POSIX conventions for exit codes:

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Success | All tasks completed successfully |
| 1 | Task execution failure | One or more tasks failed (for `task run --all`) |
| 2 | Usage/configuration error | Invalid config, bad arguments, validation failed |
| 126 | Permission denied | Cannot execute command due to permissions |
| 130 | Interrupted | User pressed Ctrl+C |

**Note:** `signalbox task run --all` attempts every task even if some fail, and exits with code 1 only after all tasks have been attempted.

## Security

Signalbox executes commands with full shell access as the invoking user. Treat task YAML files like shell scripts: only use trusted config files, and run `signalbox config check-permissions` to verify nothing is writable by other users. See [SECURITY.md](SECURITY.md) for details.

## Troubleshooting

### Tasks not running via scheduler

- Check systemd timer status: `systemctl status signalbox-<group>.timer`
- View logs: `journalctl -u signalbox-<group>.service`
- Verify cron is running: `sudo systemctl status cron`
- Check crontab: `crontab -l`

### Configuration errors

- Run `signalbox validate` to check for issues
- Verify YAML syntax
- Ensure task names match between task files and groups

### Logs not rotating

- Check `log_limit` configuration in the task definition
- Verify the log directory exists and is writable
- Run the task manually to test rotation

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

When adding features:

1. Document new patterns in the README
2. Update the `validate` command for new fields
3. Add tests (`pytest`) and keep `./dev.sh check` green

## License

MIT License — see [LICENSE](LICENSE) file for details.

Copyright (c) 2025 pdbeard
