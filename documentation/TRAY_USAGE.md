# Signalbox System Tray - Usage Guide

## Overview
The signalbox tray icon shows the status of your scheduled groups and your tasks. The tray does not run tasks. cron or systemd run them (see `signalbox export-cron` and `signalbox export-systemd`), and the tray shows the result of each run.

The color of the icon shows the results:
- **Red**: a task or a group failed, or a task or group file does not load (for example, a YAML syntax error). The tooltip names the file.
- **Yellow**: nothing failed, but a scheduled group is overdue, or a task skipped too many runs in a row. A group is overdue when its last due time went by, and it did not run. Possible causes: the cron or systemd job is not installed, the export is out of date, or the computer was asleep. A task warns after `execution.skip_warn_after` skipped runs in a row (3 by default).
- **Green**: all tasks and groups were successful.

A task or group that never ran shows in the menu as "never run". It does not change the color of the icon.

A task that signalbox skipped on purpose (its `run_if` check failed, or its last run was still running) shows as "skipped" with the reason. One skip does not change the color of the icon. A task for a different platform (`platforms`) does not show.

When a group becomes overdue, the tray also sends a desktop notification (once, unless `group_notifications.enabled` is false). On a machine without a tray, `signalbox status` shows the same information.

A group is overdue when its `schedule` was due more than 5 minutes ago (plus the time its last run took), and its last run is older than that due time.

## Installation
The tray app must have PyQt6. PyQt6 is an optional extra. To install signalbox with the tray app, use one of these commands:
```bash
pipx install ".[tray]"
# or, in a development environment
pip install -e ".[tray]"
```

## Running the Tray App
Run this command:
```bash
signalbox-tray
```

The tray icon shows in your system tray or taskbar. To start it each time you log in, see [Autostart](#autostart).

### Verbose Mode (Troubleshooting)
To print each status update and each error to the console, use `--verbose` (or `-v`):
```bash
signalbox-tray --verbose
```

## Configuration
Set the tray settings in `signalbox.yaml`:

```yaml
tray:
  enabled: true           # Enable/disable the tray icon
  poll_interval: 30       # How often to check status (seconds)
```

On a server or a system without a display, set `enabled: false`.

The tray reads the configuration and the run status again at each poll. The tray reads `enabled` and `poll_interval` only when it starts. After you change them, start the tray again.

## Tray Menu Options
Right-click the tray icon to open the menu. The menu has these items:
- **Groups**: each group, with the time of its last run, or "overdue" with the time it was due.
- **Tasks**: each task, with the time of its last run. Click a task to open its latest log.
- **Notifications**: turns on or off the desktop notifications that signalbox sends (alerts and group summaries). This replaces `alerts.notifications.enabled` and `group_notifications.enabled` for the CLI too. The tray stores this switch in `runtime/tray_state.json`, not in `signalbox.yaml`. To use the values from `signalbox.yaml` again, delete their keys from `runtime/tray_state.json`.
- **Clear error state**: the icon ignores failures that occurred before now. Overdue groups still show.
- **Open config folder**: opens the `config/` folder of your signalbox home.
- **Quit**: closes the tray app.

To run a task or a group by hand, use the CLI: `signalbox run NAME` or `signalbox group run NAME`.

## Platform Support
- **macOS**: full support
- **Linux (X11)**: full support
- **Linux (Wayland)**: the support depends on the compositor. The tray works on KDE Plasma, and on Sway with tray support.
- **Hyprland**: possibly, waybar is necessary for tray support.
- **GNOME**: limited support. Possibly, a tray extension is necessary.

## Autostart
To start the tray when you log in, do the steps for your system.

### Linux
Make the file `~/.config/autostart/signalbox-tray.desktop`:
```desktop
[Desktop Entry]
Type=Application
Name=Signalbox Tray
Exec=/home/USERNAME/.local/bin/signalbox-tray
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
```

### Compositor-specific (Hyprland, sway)
Add this line to the configuration of your compositor:
```
exec-once = signalbox-tray
```

### macOS

**Option 1: Login Items (GUI)**
1. Open **System Settings** > **General** > **Login Items**.
2. Click the **+** button. Add the full path to the signalbox-tray executable, for example `/Users/USERNAME/.local/bin/signalbox-tray`. If pipx put it in a different location, use that location.
3. The tray starts automatically when you log in.

**Option 2: launchd (advanced)**
1. Make a file at `~/Library/LaunchAgents/com.signalbox.tray.plist` with these contents:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.signalbox.tray</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/USERNAME/.local/bin/signalbox-tray</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
```
2. Load the file with this command:
```sh
launchctl load ~/Library/LaunchAgents/com.signalbox.tray.plist
```
3. The tray starts automatically when you log in.

**Note:** change the path to signalbox-tray if necessary. To find the path, use `which signalbox-tray`.

## Customization
### Custom Icons
The tray shows a single bar in the colour of the status. The icons are in the `signalbox/icons/` directory of the package:
- `green.png`: all OK
- `yellow.png`: a scheduled group is overdue
- `red.png`: a task or a group failed

They are made from the SVG files in `logo/` (`tray-icon-ok.svg`, `tray-icon-overdue.svg`, `tray-icon-failed.svg`). To change them, edit the SVG files and run `python3 generate_icons.py` from the repository root (it needs `rsvg-convert`, from librsvg). You can also replace the PNG files directly: use square PNG files of 128x128 pixels with a transparent background.

## Troubleshooting
- **The icon does not show**: make sure that your compositor has tray support. This is frequently the cause on Wayland.
- **Permission errors**: make sure that you can read and write the signalbox configuration and logs.
- **The tray stops immediately**: make sure that `tray.enabled` is `true` in the configuration.
- **The status does not change**: hold the pointer on the icon. If the tray cannot read the status, the tooltip shows the error. You can also run the tray with `--verbose`.
- **A group shows as overdue, but you did not schedule it**: the group has a `schedule` field. Remove the field, or install the job with `signalbox export-cron` or `signalbox export-systemd`.

## Possible Future Changes
- Show the status of remote signalbox instances
