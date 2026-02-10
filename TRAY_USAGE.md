# Signalbox System Tray - Usage Guide

## Overview
The Signalbox system tray provides a visual indicator of your task status directly in your system's taskbar. The icon changes color based on execution results:
- **Green**: All tasks completed successfully
- **Red**: One or more tasks failed

## Installation
The tray feature requires PyQt6, which is included in the standard installation:
```bash
pip install -e .
```

## Running the Tray App
Simply run:
```bash
signalbox-tray
```

The tray icon will appear in your system tray/taskbar.

### Verbose Mode (Troubleshooting)
For debugging and troubleshooting, run with verbose output:
```bash
signalbox-tray --verbose
# or
signalbox-tray -v
```

This will print detailed information to the console including:
- Configuration loading status
- Icon file paths and loading status
- Status update details (task counts, success/failure)
- Terminal emulator detection
- Button action execution and any errors
- Poll interval settings

Use verbose mode to diagnose issues like:
- Missing terminal emulator errors
- Icon file not found problems
- Configuration loading issues
- Runtime state polling errors

## Configuration
The tray can be configured in your `signalbox.yaml`:

```yaml
tray:
  enabled: true           # Enable/disable the tray icon
  poll_interval: 30       # How often to check status (seconds)
```

Set `enabled: false` to disable the tray in headless or server environments.

## Tray Menu Options
Right-click the tray icon to access:
- **View Status**: Opens a terminal showing task status
- **Run All Tasks**: Executes all configured tasks
- **Open Config**: Opens your config file in the default editor
- **Exit**: Closes the tray application

## Platform Support
- **Linux (X11)**: Full support
- **Linux (Wayland)**: Depends on compositor (works on KDE Plasma, Sway with tray support)
- **Hyprland**: May require waybar for tray support
- **GNOME**: Limited support; may need tray extensions

## Autostart
To run the tray on login:

### Linux
Create `~/.config/autostart/signalbox-tray.desktop`:
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
Add to your compositor config:
```
exec-once = signalbox-tray
```

## Customization
### Custom Icons
Replace the default icons in the `icons/` directory:
- `icons/green.png` - Success icon
- `icons/red.png` - Failure icon

Icons should be 64x64 PNG files for best results.

## Troubleshooting
- **Icon not showing**: Check compositor tray support, especially on Wayland
- **Permission errors**: Ensure signalbox config and logs are accessible
- **Tray disabled**: Verify `tray.enabled: true` in config
- **Buttons not working**: Run with `--verbose` to see detailed error messages. Common issues:
  - No terminal emulator found (tray will try these in order: x-terminal-emulator, gnome-terminal, konsole, xfce4-terminal, xterm, alacritty, kitty, terminator)
  - Signalbox command not in PATH
- **Status not updating**: Check verbose output for runtime state loading errors

## Future Enhancements
- Add inline status display (show task list in menu)
- Support for showing individual task status
- Integration with remote Signalbox instances
- Desktop notifications for failures
