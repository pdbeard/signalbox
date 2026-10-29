# Signalbox System Tray - Usage Guide

## Overview
The signalbox tray icon shows the status of your tasks in the system tray. The color of the icon shows the results:
- **Green**: all tasks were successful, or no task has run yet.
- **Red**: one or more tasks failed.
- **Yellow**: a run that you started from the tray is in progress.

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

The tray icon shows in your system tray or taskbar.

### Verbose Mode (Troubleshooting)
To find the cause of a problem, run the tray app with verbose output:
```bash
signalbox-tray --verbose
# or
signalbox-tray -v
```

In verbose mode, the tray app writes this data to the console:
- The status of the configuration load
- The paths of the icon files, and if the icons loaded
- The details of each status update (the number of tasks, successes and failures)
- The output of **Run All Tasks**
- The poll interval

Use verbose mode to find problems such as these:
- Icon files that the tray cannot find
- Problems when the tray loads the configuration
- Errors when the tray reads the run status

## Configuration
Set the tray settings in `signalbox.yaml`:

```yaml
tray:
  enabled: true           # Enable/disable the tray icon
  poll_interval: 30       # How often to check status (seconds)
  notify_on_success: false
```

On a server or a system without a display, set `enabled: false`.

The tray reads `signalbox.yaml` again when the file changes. Thus, changes to the notification settings and the paths apply immediately. The tray reads `enabled` and `poll_interval` only when it starts. After you change them, start the tray again.

## Tray Menu Options
Right-click the tray icon to open the menu. The menu has these items:
- **Task Status** and **Group Status**: the result and the time of the last run of each task and group
- **View Status**: opens a window with the status of all tasks
- **Run All Tasks**: runs all tasks
- **Run Group** and **Run Task**: run one group or one task. The menus are sorted by configuration file.
- **Enable Notifications**: turns `alerts.notifications.enabled` on or off
- **Notify on Success & Failure**: turns `tray.notify_on_success` on or off
- **Clear error state**: the icon ignores failures that occurred before now
- **Open Config**: opens `signalbox.yaml` in the default editor
- **Exit**: closes the tray app

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
The icons are in the `signalbox/icons/` directory of the package. To change them, replace these files:
- `green.png`: the success icon
- `red.png`: the failure icon
- `yellow.png`: the icon for a run in progress

For the best results, use PNG files of 64x64 pixels.

## Troubleshooting
- **The icon does not show**: make sure that your compositor has tray support. This is frequently the cause on Wayland.
- **Permission errors**: make sure that you can read and write the signalbox configuration and logs.
- **The tray stops immediately**: make sure that `tray.enabled` is `true` in the configuration.
- **A menu item does not work**: run the tray with `--verbose` to see the error messages.
- **The status does not change**: look in the verbose output for errors when the tray reads the run status.

## Possible Future Changes
- Show the status of remote signalbox instances
