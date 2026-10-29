# Notifications Guide

Signalbox can send desktop notifications on macOS and Linux. There are two types of notifications:
1. **Alert notifications**: signalbox sends one when the task output matches an alert pattern.
2. **Group notifications**: signalbox sends a summary after a group runs.

## Features

- **macOS and Linux:** the notifications work on the two systems.
- **Failures only:** by default, signalbox sends notifications only for failures. You can change this.
- **Settings for each alert:** an alert can have its own notification settings.
- **Titles:** you can set the notification title of each alert.
- **Summaries:** a group notification shows the number of tasks that passed and failed, and the names of the failed tasks.
- **Urgency levels:** on Linux, failure notifications are critical.
- **No extra packages:** signalbox uses the tools of the operating system (osascript on macOS, notify-send on Linux).

## Configuration

Add these sections to `~/.config/signalbox/config/signalbox.yaml`:

```yaml
# Alert notifications (when task output matches alert patterns)
alerts:
  notifications:
    enabled: true          # Enable/disable alert notifications
    on_failure_only: true  # Only notify for critical/warning (not info)

# Group notifications (summary after running groups)
group_notifications:
  enabled: true            # Enable/disable group summary notifications
  on_failure_only: true    # Only notify when tasks in the group fail
  show_failed_names: true  # Include failed task names
```

### Alert Notification Options

- **`alerts.notifications.enabled`** (default: `true`): turns alert notifications on or off for all tasks.
- **`alerts.notifications.on_failure_only`** (default: `true`): if true, signalbox sends notifications only for `critical` and `warning` alerts. It does not send them for `info` alerts.
- **`alerts.notifications.cooldown_minutes`** (default: `60`): after an alert sends a notification, the same task and pattern do not send a notification again in this number of minutes. Signalbox records each alert. `signalbox alerts` shows all of them. Set `0` to send a notification on each run.

On Linux, scheduled runs (cron and systemd) usually do not have `DBUS_SESSION_BUS_ADDRESS`. In this condition, signalbox uses `/run/user/<uid>/bus`. Thus, notifications get to your desktop while you are logged in.

### Alert Retention

Signalbox deletes old alerts from the alert history after each run of a task. These settings control which alerts it keeps:

```yaml
alerts:
  retention:
    max_days: 30        # Keep alerts for 30 days
    max_entries: 1000   # Keep at most 1000 alerts per task
    per_severity:       # Replaces max_days for these severities
      critical: 90
      warning: 30
      info: 7
```

- **`alerts.retention.max_days`** (default: `30`): signalbox deletes alerts that are older than this number of days.
- **`alerts.retention.max_entries`** (default: `1000`): each task keeps this number of alerts or fewer. Signalbox deletes the oldest alerts first.
- **`alerts.retention.per_severity`** (default: critical `90`, warning `30`, info `7`): the number of days to keep alerts of each severity. For a severity in this list, this value replaces `max_days`.

### Group Notification Options

- **`group_notifications.enabled`** (default: `true`): turns the group summary notifications on or off.
- **`group_notifications.on_failure_only`** (default: `true`): if true, signalbox sends a notification only when a task fails. If false, it sends a notification after each group run.
- **`group_notifications.show_failed_names`** (default: `true`): if true, and 3 or fewer tasks failed, the message has the names of the failed tasks.

### Tray Notification Options

- **`tray.notify_on_success`** (default: `false`): if true, the tray shows a message when a run that it started is successful. The tray always shows failures while notifications are on. The tray menu item "Notify on Success & Failure" changes this setting. This setting does not change alert notifications.

## Testing Notifications

To test notifications without a task run, use these commands:

```bash
# Basic test
signalbox notify-test

# Custom test with your own message
signalbox notify-test --title "My Title" --message "My message"

# Test urgency levels (Linux only)
signalbox notify-test --urgency critical
```

## Notification Messages

### Success (when `on_failure_only: false`)
```
Title: Signalbox - Success
Message: All tasks ran successfully (5/5)
```

### Partial Failure
```
Title: Signalbox - Failures Detected
Message: Ran 5 tasks: 3 passed, 2 failed
Failed: backup.sh, sync.py
```

### Complete Failure
```
Title: Signalbox - Failures Detected
Message: Ran 3 tasks: 0 passed, 3 failed
```

## Platform Requirements

### macOS
- **Built-in support:** signalbox uses `osascript`. macOS includes it.
- You do not have to install more software.

### Linux
- **Necessary:** the `notify-send` command. It is usually in the `libnotify-bin` package or the `notification-daemon` package.
- **Installation:**
  ```bash
  # Debian/Ubuntu
  sudo apt-get install libnotify-bin
  
  # Fedora/RHEL
  sudo dnf install libnotify
  
  # Arch
  sudo pacman -S libnotify
  ```

## Integration with Scheduling

When cron or a systemd timer runs signalbox, notifications also show for tasks that run in the background.

Use `signalbox export-cron GROUP` or `signalbox export-systemd GROUP` to make
the schedule entry. Do not write it by hand. The export uses the `schedule` of
the group, the absolute path to signalbox and the correct `SIGNALBOX_HOME`.
Cron does not supply these items.

```bash
signalbox export-cron scheduled
```

If notifications do not show, do these checks:
1. Examine the `alerts.notifications.enabled` and `group_notifications.enabled` settings in your configuration.
2. On Linux, make sure that `notify-send` is installed.
3. Make sure that your desktop environment can show notifications.
4. Look for warnings in the output of signalbox (stderr).

## Troubleshooting

### macOS: notifications do not show
- In System Settings → Notifications, make sure that notifications from the terminal are on.
- Make sure that the terminal app has permission to show notifications.

### Linux: notifications do not show
- Make sure that `notify-send` is installed: `which notify-send`
- Test it manually: `notify-send "Test" "Message"`
- Make sure that your desktop environment can show notifications.
- For cron jobs, make sure that you are logged in to the desktop. Signalbox uses the session bus of your login session.

### Silent Failures
If a notification fails, signalbox writes a warning to stderr. The task run continues and its result does not change. For scheduled runs, look for the warning in the cron mail or in `journalctl`.

## Per-Alert Overrides

An alert in a task file can have its own notification settings. These settings replace the global settings for that alert:

```yaml
tasks:
  - name: check_website
    command: ./check.sh
    alerts:
      - pattern: "^OK"
        message: "Website is up"
        severity: info
        notify: true           # Override: send notification even for info
        on_failure_only: false # Override: always notify for this alert
      - pattern: "^DOWN"
        message: "Website is down!"
        severity: critical
        notify: false          # Override: disable notification for this alert
```

**Override precedence:**
1. The setting of the alert (`notify`, `on_failure_only`). This has the highest priority.
2. The global setting (`alerts.notifications.*`). Signalbox uses it if the alert does not have a setting.

## Examples

### Alert notifications only for critical/warning
```yaml
alerts:
  notifications:
    enabled: true
    on_failure_only: true  # Skip info alerts
```

### Group notifications only on failures
```yaml
group_notifications:
  enabled: true
  on_failure_only: true
  show_failed_names: true
```

### Always notify for both alerts and groups
```yaml
alerts:
  notifications:
    enabled: true
    on_failure_only: false  # Notify for all severities

group_notifications:
  enabled: true
  on_failure_only: false  # Notify on success too
```

### Disable all notifications
```yaml
alerts:
  notifications:
    enabled: false

group_notifications:
  enabled: false
```

## Possible Future Changes

We can add these features in a later version:
- Windows support
- Notification sounds that you can change
- Email and webhook notifications
- Notification settings for each group
