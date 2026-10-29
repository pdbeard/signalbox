![signalbox logo](logo_ideas/event-portal-blocks.svg)

# signalbox

Signalbox is a command-line tool that runs and monitors shell tasks. It keeps a log of each run and records alerts that match the task output. It also runs tasks in groups and makes schedule files for systemd and cron.

## Main Features

- Show each task and the status of its last run
- Run one task, or a group of tasks in series or in parallel
- Keep one log for each run, and delete old logs by count, age or size
- Record alerts when task output matches a pattern, and send desktop notifications
- Make systemd and cron files for scheduled groups
- Show a red or green status in the system tray (optional)

## Installation

### Recommended: Global Install with pipx

If pipx is not installed, install it:

    python3 -m pip install --user pipx
    python3 -m pipx ensurepath

Then install signalbox from your local copy of the source:

    pipx install .

    # With the system tray app:
    pipx install ".[tray]"

pipx installs signalbox in its own environment. You can then use the `signalbox` command in all directories.

### Local Development Install

To change or test signalbox, use a virtual environment:

    python3 -m venv venv
    source venv/bin/activate
    pip install -e ".[dev]"

During development, you can run signalbox from the project directory. You do not have to install it:

```bash
python -m signalbox list  # Uses ./config/ in the current directory if present
```

### Initialize Configuration

After you install signalbox, make the configuration directory:

```bash
signalbox init
```

This command makes `~/.config/signalbox/` with these items:

- The global configuration file (`config/signalbox.yaml`)
- The directory for task files (`config/tasks/`)
- The directory for group files (`config/groups/`)
- Example tasks and groups (`config/catalog/`). Signalbox does not load them. To load them, set `include_catalog: true`.
- The log directory (`logs/`)
- The directory for run status (`runtime/`)

You can now use `signalbox` in all directories.

### Configuration Location

Signalbox looks for its configuration in these locations, in this sequence:

1. **`$SIGNALBOX_HOME`**: a location that you set with this environment variable. This location has the highest priority.
2. **`$XDG_CONFIG_HOME/signalbox`**: the XDG location. Signalbox uses it only if `XDG_CONFIG_HOME` has a value.
3. **`~/.config/signalbox/`**: the user configuration directory. `signalbox init` makes it.
4. **The current directory**: for development or for the configuration of one project. Signalbox uses it only if `./config/signalbox.yaml` is in the directory.

```bash
# Explicit override
export SIGNALBOX_HOME=/path/to/your/config
signalbox list

# Or point at a specific signalbox.yaml for one invocation
signalbox --config /path/to/config/signalbox.yaml list
```

## Commands

### Setup

- `signalbox init`: make the configuration directory. Do this one time after you install signalbox.

### Shortcuts

- `signalbox list`: show all tasks, with their status and the time of the last run
- `signalbox run NAME`: run a task
- `signalbox validate`: examine the configuration files for errors

### Tasks

- `signalbox task list`: show all tasks, in groups by configuration file
- `signalbox task run NAME`: run one task. The command shows the first lines of the output. To stop this, use `--quiet`.
- `signalbox task run --all`: run all tasks

### Groups

- `signalbox group list`: show all groups and their tasks
- `signalbox group run NAME`: run all tasks in a group, in series or in parallel
- `signalbox list-schedules`: show the scheduled groups and their cron expressions

### Logs

- `signalbox log show TASK`: show the newest log of a task
- `signalbox log history TASK`: show all the logs of a task
- `signalbox log list [--task NAME] [--failed] [--today] [--since DATE] [--last N] [-v]`: show the runs of all tasks
- `signalbox log tail TASK`: show the newest log of a task. Then show the log of each new run when that run is complete.
- `signalbox log clear --task NAME` / `signalbox log clear --all`: delete the logs and the alert history

### Configuration

- `signalbox config show [KEY]`: show all settings, or one setting (for example, `config show execution.default_timeout`)
- `signalbox config path`: show the configuration directory
- `signalbox config check-permissions`: show a warning if other users can read or write the configuration files or the logs
- `signalbox config validate`: examine the configuration files for errors

### Alerts & Notifications

- `signalbox alerts [TASK] [--severity LEVEL] [--days N]`: show the recent alerts
- `signalbox notify-test`: send a test desktop notification

### Scheduling Exports

- `signalbox export-systemd GROUP [--user]`: make the systemd service file and timer file
- `signalbox export-cron GROUP`: make a crontab line

### Tray App

- `signalbox-tray`: a system tray icon that shows the task status. You must install it with `pip install "signalbox[tray]"`.

For more information, refer to [documentation/TRAY_USAGE.md](documentation/TRAY_USAGE.md).

## Configuration

### Tasks (`config/tasks/`)

Signalbox loads all `*.yaml` and `*.yml` files in this directory. This is an example of `config/tasks/system.yaml`:

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

Each task must have these fields:

- `name`: a name that no other task uses
- `command`: the shell command to run
- `description`: a short description for people

These fields are optional:

- `timeout`: the time limit for the task, in seconds. It replaces `execution.default_timeout` for this task. A value of 0 removes the time limit. If the task runs longer than the time limit, signalbox stops the task and all processes that it started.
- `cwd`: the working directory. Use an absolute path, or a path relative to the signalbox home. If you do not set it, signalbox uses the signalbox home. This is the same for manual runs and scheduled runs.
- `log_limit`: the rule to delete old logs. `type: count` keeps the N newest logs. `type: age` keeps the logs of the last N days. `type: size` keeps the newest logs that fit in N MB.
- `alerts`: the patterns to find in the output. Refer to "Alerting" below.

Commands get no input (stdin is `/dev/null`). Thus, a command that asks for input stops with an error immediately. It does not wait until the time limit.

**How to organize the files:** you can put tasks in different files by function (`basic.yaml`, `backup.yaml`), by environment (`production.yaml`, `staging.yaml`), or by team.

### Groups (`config/groups/`)

A group is a set of tasks that run together. This is an example of `config/groups/daily.yaml`:

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

- `name`, `description` and `tasks` are necessary.
- `execution`: `serial` (the default) or `parallel`.
- `stop_on_error`: for serial groups only. If a task fails, signalbox does not run the remaining tasks.
- `schedule`: a cron expression (optional). You can export only scheduled groups to systemd or cron.

You can schedule only groups. To schedule one task, put it in a group of its own.

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

Signalbox does not have its own scheduler. It makes systemd or cron files. You examine and install these files. You can export only groups that have a `schedule` field.

Signalbox writes the files in the signalbox home (`~/.config/signalbox` by default). The export command shows the paths and the installation steps.

### Option 1: systemd (user units, recommended)

```bash
# Generate files in ~/.config/signalbox/systemd/daily/
signalbox export-systemd daily --user

# Install
mkdir -p ~/.config/systemd/user
cp ~/.config/signalbox/systemd/daily/signalbox-daily.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now signalbox-daily.timer

# Check status
systemctl --user status signalbox-daily.timer
```

User units run only while you are logged in. To run them at other times, use `loginctl enable-linger $USER`.

To make a system unit, run `signalbox export-systemd daily` without `--user`. Then copy the files to `/etc/systemd/system/` with `sudo`. The service has `User=<you>`. Thus, the tasks run as your user, not as root.

### Option 2: cron

```bash
# Generate entry (creates cron/<group>/ directory)
signalbox export-cron daily

# Add to crontab
crontab -e
# Paste the generated line
```

## Alerting

Signalbox compares the task output with patterns. When a pattern matches, signalbox records an alert. It can also send a desktop notification.

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

- `pattern` (necessary): the regular expression or text to find in the task output (stdout or stderr)
- `message` (necessary): the text that signalbox records and shows in the notification
- `severity` (optional): `info`, `warning` or `critical`. The default is `info`.
- `title` (optional): the title of the notification. The default is `"Alert: {task_name}"`.
- `notify` (optional): replaces the global notification setting for this alert
- `on_failure_only` (optional): if true, signalbox sends a notification only for `warning` and `critical` alerts

### Viewing Alerts

```bash
signalbox alerts                                # all recent alerts
signalbox alerts disk_check --severity critical # filter by task and severity
```

Signalbox keeps alerts in `logs/<task_name>/alerts/alerts.jsonl`. It deletes old alerts as the retention settings in `signalbox.yaml` tell it.

For all notification settings, refer to [documentation/NOTIFICATIONS.md](documentation/NOTIFICATIONS.md).

## Validation

Before you install a schedule, examine your configuration:

```bash
signalbox validate
```

This command finds these problems:

- Necessary fields that are missing
- Names that two or more tasks (or groups) use
- Groups that refer to tasks that do not exist
- Incorrect task time limits
- Cron expressions that are possibly incorrect (shown as warnings)
- YAML errors

## Documentation

The `documentation/` directory has these guides:

- **[Configuration Guide](documentation/CONFIG_GUIDE.md)**: global settings, tasks and groups
- **[Writing Scripts Guide](documentation/WRITING_SCRIPTS.md)**: how to write scripts that work well with signalbox
- **[File Structure](documentation/FILE_STRUCTURE.md)**: the directories, and how to use more than one file
- **[Config System](documentation/CONFIG_SYSTEM.md)**: a summary of the configuration system
- **[Execution Modes](documentation/EXECUTION_MODES.md)**: how groups run in parallel or in series
- **[Scheduling Examples](documentation/SCHEDULING_EXAMPLES.md)**: examples of schedules
- **[Notifications](documentation/NOTIFICATIONS.md)**: the settings for desktop notifications
- **[Tray Usage](documentation/TRAY_USAGE.md)**: the system tray app

## Exit Codes

Signalbox uses the POSIX rules for exit codes:

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Success | All tasks ran correctly |
| 1 | A task failed | A task failed (`task run`), or one or more tasks failed (`task run --all`, `group run`) |
| 2 | Usage or configuration error | Incorrect configuration, incorrect arguments, or errors from `validate` |
| 126 | Permission denied | The user does not have permission to run the command |
| 130 | Interrupted | The user pushed Ctrl+C |

**Note:** `signalbox task run --all` tries to run all tasks, also when some tasks fail. It exits with code 1 after it tries all tasks. `signalbox group run` exits with code 1 if a task in the group failed, or if `stop_on_error` stopped a task. Thus, cron and systemd see the failure.

## Security

Signalbox runs commands in a shell, with all the permissions of the user who starts it. Think of task YAML files as shell scripts. Use only configuration files that you trust. To make sure that other users cannot change them, run `signalbox config check-permissions`. For more information, refer to [SECURITY.md](SECURITY.md).

## Troubleshooting

### Scheduled tasks do not run

- Examine the status of the systemd timer: `systemctl status signalbox-<group>.timer`
- Examine the logs: `journalctl -u signalbox-<group>.service`
- Make sure that cron runs: `sudo systemctl status cron`
- Examine the crontab: `crontab -l`

### Configuration errors

- Run `signalbox validate` to find problems.
- Make sure that the YAML syntax is correct.
- Make sure that the task names in the groups are the same as the names in the task files.

### Old logs are not deleted

- Examine the `log_limit` setting of the task.
- Make sure that the log directory exists and that you can write to it.
- Run the task manually. Then make sure that signalbox deleted the old logs.

## Contributing

You can send a pull request.

When you add a feature:

1. Write about new patterns in the README.
2. Change the `validate` command for new fields.
3. Add tests (`pytest`). Make sure that `./dev.sh check` has no errors.

## License

MIT License. For more information, refer to the [LICENSE](LICENSE) file.

Copyright (c) 2025 pdbeard
