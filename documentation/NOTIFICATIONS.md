# Notifications Guide

Signalbox includes a cross-platform desktop notification system with two types of notifications:
1. **Alert notifications** - When task output matches alert patterns
2. **Group notifications** - Summary after running groups of tasks

## Features

- **Cross-platform support:** Works on macOS and Linux
- **Smart notifications:** Only notify on failures by default (configurable)
- **Per-alert overrides:** Control notifications at the alert level
- **Custom titles:** Set custom notification titles for alerts
- **Summary messages:** Shows pass/fail counts and failed task names
- **Urgency levels:** Critical notifications for failures (Linux)
- **Zero dependencies:** Uses native OS tools (osascript on macOS, notify-send on Linux)

## Configuration

Add these sections to your `~/.config/signalbox/config/signalbox.yaml`:

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

- **`alerts.notifications.enabled`** (default: `true`): Enable/disable alert notifications globally
- **`alerts.notifications.on_failure_only`** (default: `true`): If true, only send notifications for critical/warning alerts (not info severity)

### Group Notification Options

- **`group_notifications.enabled`** (default: `true`): Enable/disable group execution summary notifications
- **`group_notifications.on_failure_only`** (default: `true`): If true, only send notifications when tasks fail; if false, always notify
- **`group_notifications.show_failed_names`** (default: `true`): If true and ≤3 tasks failed, include their names in the notification message

## Testing Notifications

Test your notification system without running any scripts:

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
Message: All scripts ran successfully (5/5)
```

### Partial Failure
```
Title: Signalbox - Failures Detected
Message: Ran 5 scripts: 3 passed, 2 failed
Failed: backup.sh, sync.py
```

### Complete Failure
```
Title: Signalbox - Failures Detected
Message: Ran 3 scripts: 0 passed, 3 failed
```

## Platform Requirements

### macOS
- **Built-in support:** Uses `osascript`, which is included with macOS
- No additional installation required

### Linux
- **Requires:** `notify-send` command (usually from `libnotify-bin` or `notification-daemon` package)
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

When running Signalbox via cron or systemd timer, notifications will appear even when the scripts run in the background:

```cron
# Run every hour and notify on failures
0 * * * * /path/to/signalbox run-group scheduled
```

If notifications aren't appearing, check:
1. The `notifications.enabled` setting in your config
2. That `notify-send` is installed (Linux)
3. That your desktop environment supports notifications
4. Log files for any error messages

## Troubleshooting

### macOS: Notifications not appearing
- Ensure System Preferences → Notifications allows terminal/script notifications
- Check that the terminal app has notification permissions

### Linux: Notifications not appearing
- Verify `notify-send` is installed: `which notify-send`
- Test manually: `notify-send "Test" "Message"`
- Check if your desktop environment supports system tray notifications
- Ensure `DISPLAY` environment variable is set (for cron jobs, you may need to export it)

### Silent Failures
Signalbox will log warnings if notifications fail but won't crash script execution. Check logs at `~/.config/signalbox/logs/` for details.

## Per-Alert Overrides

You can override notification settings for individual alerts in your task configuration:

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
1. Per-alert setting (`notify`, `on_failure_only`) - highest priority
2. Global setting (`alerts.notifications.*`) - fallback

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

## Future Enhancements

Planned features for future releases:
- System tray icon with persistent status indicator
- Windows support
- Customizable notification sounds
- Email/webhook notifications
- Per-group notification settings
