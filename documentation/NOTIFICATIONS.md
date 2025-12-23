# Notifications Guide

Signalbox includes a cross-platform desktop notification system that can alert you when scripts complete, especially useful for monitoring scheduled executions.

## Features

- **Cross-platform support:** Works on macOS and Linux
- **Smart notifications:** Only notify on failures by default (configurable)
- **Summary messages:** Shows pass/fail counts and failed script names
- **Urgency levels:** Critical notifications for failures (Linux)
- **Zero dependencies:** Uses native OS tools (osascript on macOS, notify-send on Linux)

## Configuration

Add a `notifications` section to your `~/.config/signalbox/config/signalbox.yaml`:

```yaml
notifications:
  enabled: true              # Enable/disable notifications
  on_failure_only: true      # Only notify when scripts fail (recommended)
  show_failed_names: true    # Include names of failed scripts (up to 3)
```

### Configuration Options

- **`enabled`** (default: `true`): Master switch for notifications
- **`on_failure_only`** (default: `true`): If true, only send notifications when scripts fail; if false, always notify
- **`show_failed_names`** (default: `true`): If true and ≤3 scripts failed, include their names in the notification message

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

## Examples

### Notify only on critical failures
```yaml
notifications:
  enabled: true
  on_failure_only: true
  show_failed_names: true
```

### Always notify (useful for important scheduled tasks)
```yaml
notifications:
  enabled: true
  on_failure_only: false
  show_failed_names: true
```

### Disable notifications
```yaml
notifications:
  enabled: false
```

## Future Enhancements

Planned features for future releases:
- System tray icon with persistent status indicator
- Windows support
- Customizable notification sounds
- Email/webhook notifications
- Per-group notification settings
