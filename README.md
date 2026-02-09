![signalbox logo](logo_ideas/event-portal-blocks.svg)
# signalbox 
signalbox is a CLI tool for managing, executing, and monitoring scripts with detailed logging, scheduling, and group execution capabilities. 

## Main Features

-  List scripts and their last run status
-  Run individual scripts or script groups
-  Logs and execution history
-  Parallel or serial execution modes
-  Automatic log rotation (by count or age)
-  Generate systemd/cron configurations 


## Installation

### Recommended: Global Install with pipx

Install pipx if you don't have it:

    python3 -m pip install --user pipx
    python3 -m pipx ensurepath

Then install signalbox globally from your local source:

    pipx install .

This makes the `signalbox` command available globally, in an isolated environment.

### Local Development Install

If you want to develop or test signalbox locally, you can also use a virtual environment:

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e .[dev]

When developing, you can run directly from the project directory without `signalbox init`:
```bash
python signalbox.py list  # Uses config/ in current directory
```
This does not install globally.

### Initialize Configuration
After installation, set up your configuration directory:
```bash
signalbox init
```

This creates `~/.config/signalbox/` with:
- Default configuration file (`config/signalbox.yaml`)
- Example scripts directory (`config/scripts/`)
- Example groups directory (`config/groups/`)
- Log directory (`logs/`)
- Runtime state directory (`runtime/`)

**You can now run `signalbox` from any directory on your system!**

### Configuration Location
Signalbox looks for configuration in the following order:
1. **`$SIGNALBOX_HOME`** - Custom location via environment variable (highest priority)
2. **`$XDG_CONFIG_HOME/signalbox`** - XDG Base Directory specification (if XDG_CONFIG_HOME is set)
3. **`~/.config/signalbox/`** - User configuration directory (created by `signalbox init`)
4. **Current directory** - For development or project-specific configurations (if `config/signalbox.yaml` exists)

**Custom location examples:**
```bash
# Explicit override
export SIGNALBOX_HOME=/path/to/your/config
signalbox list  # Uses config from custom location

# XDG Base Directory support
export XDG_CONFIG_HOME=~/.local/config
signalbox init  # Creates config in ~/.local/config/signalbox

# Development/local config
cd /path/to/project
signalbox list  # Uses ./config/signalbox.yaml if it exists
```

**Note:** If you have `XDG_CONFIG_HOME` set from testing, you can clear it with:
```bash
unset XDG_CONFIG_HOME
```

## DEMO VID? 

## Commands

### Setup
- `init` - Initialize configuration in ~/.config/signalbox/ (run once after installation)

### Script Management
- `list` - Show all scripts with status and last run time
- `run <name>` - Execute a specific script
- `run-all` - Execute all scripts sequentially
- `run-group <name>` - Execute all scripts in a group

### Group Management
- `list-groups` - Show all groups and their scripts
- `list-schedules` - Show scheduled groups with cron expressions

### Log Management
- `logs <name>` - View the latest log for a script
- `log-history <name>` - List all historical runs for a script
- `clear-logs <name>` - Clear logs for a specific script
- `clear-all-logs` - Clear all logs for all scripts

### Configuration Management
- `show-config` - Display all global configuration settings
- `get-setting <key>` - Get a specific config value (e.g., `execution.default_timeout`)
- `validate` - Validate configuration files

### Automation & Scheduling
- `export-systemd <group>` - Generate systemd service/timer files
- `export-cron <group>` - Generate crontab entry
`** - Group definitions and scheduling (all .yaml files loaded)

- See [documentation/FILE_STRUCTURE.md](documentation/FILE_STRUCTURE.md) for detailed examples

### Scripts Directory (`scripts/`)

Example `scripts/basic.yaml`:
```yaml
scripts:
    command: date
    description: Show current date and time
```

Example `scripts/system.yaml`:
```yaml
scripts:
  - name: system_uptime
    command: uptime
    description: Show system uptime
    log_limit:
      type: age
      value: 7
```

**Organization tips:**
- Split by functionality: `basic.yaml`, `system.yaml`, `backup.yaml`
- Split by environment: `production.yaml`, `staging.yaml`
- Split by team: `devops.yaml`, `database.yaml`

### Groups Directory (`groups/`)

Example `groups/basic.yaml`:
```yaml
groups:
  - name: basic
    description: Basic system info
    execution: parallel
    scripts:
      - hello
      - show_date
```

Example `groups/scheduled.yaml`:
```yaml
groups:
  - name: daily
    description: Daily maintenance tasks
    schedule: "0 2 * * *"  # 2 AM daily
    scripts:
      - backup
      - cleanup
  
  - name: monitoring
    description: System monitoring
    schedule: "*/5 * * * *"  # Every 5 minutes
    scripts:
      - cpu_check
      - disk_check
```

**Organization tips:**
- Split by schedule: `daily.yaml`, `hourly.yaml`, `manual.yaml`
- Split by purpose: `monitoring.yaml`, `maintenance.yaml`
- Split by environment: `prod-groups.yaml`, `dev-groups.yaml`

### Scripts Configuration

Each script requires:
- `name` - Unique identifier
- `command` - Shell command to execute
- `description` - Human-readable description

Optional fields:
- `log_limit` - Log rotation configuration
  - `type: count` - Keep N most recent logs
  - `type: age` - Keep logs for N days

#### Log Examples 
```yaml
log_limit:
  type: count
  value: 5  # Keep 5 most recent logs
```

```yaml
log_limit:
  type: age
  value: 7  # Keep logs for 7 days
```

### Groups Configuration

Groups organize scripts into logical collections:
- `name` - Unique group identifier
- `description` - Purpose of the group
- `scripts` - List of script names
- `schedule` - (Optional) Cron expression for automation

* Only groups can be scheduled, individual scripts needing unique schedules can be added as a single script to a group.  


### Scheduling Examples

```yaml
groups:
  # Every 5 minutes
  - name: monitoring
    schedule: "*/5 * * * *"
    scripts: [cpu, disk, memory]
  
  # Hourly at minute 0
  - name: hourly-tasks
    schedule: "0 * * * *"
    scripts: [log_rotate, temp_cleanup]
  
  # Daily at 2 AM
  - name: daily
    schedule: "0 2 * * *"
    scripts: [backup, reports]
  
  # Weekly on Sunday at 3 AM
  - name: weekly
    schedule: "0 3 * * 0"
    scripts: [full_backup, audit]
  
  # Every 15 minutes (single script)
  - name: critical-sync
    schedule: "*/15 * * * *"
    scripts: [sync_critical_data]
```

## Automation Setup

Currently, signalbox simply generates the config files for you to add at your discretion.

**Note:** Only groups that have a `schedule` field (cron expression) can be exported using `export-systemd` or `export-cron`. Attempting to export a group without a schedule will result in an error. Be sure your group YAML includes a `schedule` if you want to automate it.

### Option 1: systemd 
Generate systemd files for a scheduled group:

```bash
# Generate files (creates systemd/<group>/ directory)
python signalbox.py export-systemd daily

# Install (requires root)
sudo cp systemd/daily/signalbox-daily.service systemd/daily/signalbox-daily.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable signalbox-daily.timer
sudo systemctl start signalbox-daily.timer

# Check status
sudo systemctl status signalbox-daily.timer
```

**Note:** Generated files are exported to `systemd/<group_name>/` directory for better organization.

For user-level (no root):
```bash
python signalbox.py export-systemd daily --user
```

### Option 2: cron 

Generate crontab entry:

```bash
# Generate entry (creates cron/<group>/ directory)
python signalbox.py export-cron daily

# Add to crontab
crontab -e
# Paste the generated line
```



## Alerting

Signalbox supports task output pattern alerts for monitoring and notification.

### Defining Alerts in Tasks

Add an `alerts` section to any task definition:

```yaml
tasks:
  - name: disk_check_test
    command: ./check_disk.sh
    description: Check disk usage
    alerts:
      - pattern: "Disk usage is above 80%"
        title: "Disk Space Critical"
        message: "Disk usage is above 80%!"
        severity: critical
      - pattern: "Disk usage is above 60%"
        title: "Disk Space Warning"
        message: "Disk usage is above 60%"
        severity: warning
      - pattern: "Disk OK"
        message: "Disk usage is normal"
        severity: info
        notify: false  # Don't send notification for this alert
```

**Alert fields:**
- `pattern` (required): Regex or substring to match in task output (stdout or stderr)
- `message` (required): Message to log and notify if pattern is matched
- `severity` (optional): `info`, `warning`, or `critical` (default: `info`)
- `title` (optional): Custom notification title (default: `"Alert: {task_name}"`)
- `notify` (optional): Override global notification setting for this alert
- `on_failure_only` (optional): If true, only send notification for warning/critical severity

When a task runs, if any alert pattern matches the output, the alert is logged and (optionally) a desktop notification is sent based on your configuration.

### Viewing Alerts

List recent alerts:
```bash
signalbox alerts
```
Filter by task name or severity:
```bash
signalbox alerts disk_check_test --severity critical
```

Alerts are stored in `logs/<task_name>/alerts/alerts.jsonl`.

See [documentation/NOTIFICATIONS.md](documentation/NOTIFICATIONS.md) for full alert notification configuration options.

---
## Validation

Before deploying schedules, validate your configuration:

```bash
python signalbox.py validate
```

This checks for:
- Missing required fields
- Duplicate names
- Non-existent script references
- Invalid cron syntax
- Configuration errors


## Documentation

Comprehensive guides are available in the `documentation/` directory:

- **[Configuration Guide](documentation/CONFIG_GUIDE.md)** - How to configure global settings, scripts, and groups
- **[Writing Scripts Guide](documentation/WRITING_SCRIPTS.md)** - Best practices for writing scripts that work with signalbox
- **[File Structure](documentation/FILE_STRUCTURE.md)** - Understanding the project layout and multi-file organization
- **[Config Reference](documentation/CONFIG_REFERENCE.md)** - Complete reference of all configuration options
- **[Config System](documentation/CONFIG_SYSTEM.md)** - Overview of the three-file configuration system
- **[Execution Modes](documentation/EXECUTION_MODES.md)** - Parallel vs serial execution explained
- **[Scheduling Examples](documentation/SCHEDULING_EXAMPLES.md)** - Real-world scheduling patterns and examples


## Exit Codes

Signalbox follows POSIX conventions for exit codes:

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Success | All tasks completed successfully |
| 1 | Task execution failure | One or more tasks failed (for `task run --all`) |
| 2 | Usage/configuration error | Invalid config, bad arguments, validation failed |
| 126 | Permission denied | Cannot execute command due to permissions |
| 130 | Interrupted | User pressed Ctrl+C |

**Important:** When running multiple tasks with `signalbox task run --all`, all tasks will be attempted even if some fail. The command exits with code 1 only after all tasks have been attempted.


## Troubleshooting

### Scripts not running via scheduler
- Check systemd timer status: `systemctl status signalbox-<group>.timer`
- View logs: `journalctl -u signalbox-<group>.service`
- Verify cron is running: `sudo systemctl status cron`
- Check crontab: `crontab -l`

### Configuration errors
- Run `python signalbox.py validate` to check for issues
- Verify YAML syntax
- Ensure script names match between scripts and groups

### Logs not rotating
- Check `log_limit` configuration in script definition
- Verify log directory exists and is writable
- Run script manually to test rotation

## Examples

See `config.yaml` for a complete example with:
- Scripts with various commands
- Multiple groups
- Scheduled and unscheduled groups
- Singleton group pattern
- Different log rotation strategies

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

When adding features:
1. Document any new patterns in README
2. Update `validate` command for new fields
3. Other stuff I'm sure will be needed if anyone actually contributes 0.o

## License

MIT License - See [LICENSE](LICENSE) file for details

Copyright (c) 2025 pdbeard