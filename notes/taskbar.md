# Design Decisions

## Minimum Functionality
- Tray icon (red/green) shows overall script status (success/failure)
- Tooltip or click highlights status of scripts (list of successes/failures)

## Ideal Functionality
- Tray menu allows control over Signalbox:
  - Adjust how often scripts run (interval/schedule)
  - View detailed status of scripts, groups, and runtime
  - Run scripts/groups directly from tray
  - Add, modify, or remove scripts/groups

## GUI vs. Tray Menu
- Basic status and control (run/view) can be handled with a tray menu
- Advanced features (editing scripts/groups, full runtime view) require a proper GUI application
- Consider starting with tray-only, then expanding to a full GUI if advanced control is needed

---

## Implementation Status ✅

**COMPLETED** - Basic tray implementation using PyQt6:
- ✅ PyQt6 dependency added to requirements.txt and pyproject.toml
- ✅ Created `core/tray_app.py` with basic tray functionality
- ✅ Green/red status icons created in `icons/` directory
- ✅ Configuration options added to `signalbox.yaml`
- ✅ Entry point `signalbox-tray` added for easy launching
- ✅ Basic menu with View Status, Run All Tasks, Open Config, Exit
- ✅ Polling runtime state to update icon color
- ✅ Usage documentation created in `TRAY_USAGE.md`

**Current Features:**
- System tray icon with green (success) / red (failure) status
- Tooltip showing task summary
- Right-click menu for basic control
- Configurable polling interval
- Enable/disable via config

**Future Enhancements:**
- Inline task list in tray menu
- Per-task status display
- Desktop notifications for failures
- Remote Signalbox instance integration
- Full GUI for advanced editing

---

# Signalbox Taskbar Integration Guide

This guide outlines the steps to create a system tray (taskbar) entry for Signalbox, with status indication (green/red icon) based on script success. It also highlights platform and compositor differences (Wayland, X11, Hyperland, etc.).

## 1. Choose a Tray Library
- **Recommended:** [pystray](https://github.com/moses-palmer/pystray) (cross-platform, supports X11, some Wayland compositors)
- **Alternatives:** Qt (PyQt/PySide), GTK, Electron (for advanced UI)

## 2. Create Tray App Script
- Add a new script (e.g., `signalbox_tray.py`)
- Use pystray to create a tray icon
- Define menu actions: Run scripts, Show logs, Open config, Exit
- Set icon color:
  - **Green:** All scripts ran successfully
  - **Red:** One or more scripts failed
- Periodically check script status (poll logs or runtime state)

## 3. Platform Differences
### X11 (Traditional Linux)
- pystray works well
- Most bars (Polybar, i3bar, xfce4-panel, etc.) support tray icons
- No special configuration needed

### Wayland (Modern Linux)
- **Support varies by compositor:**
  - **Sway:** Supports tray via [wlroots](https://github.com/swaywm/wlroots)
  - **Hyprland:** Tray support is experimental; may require [waybar](https://github.com/Alexays/Waybar)
  - **KDE Plasma:** Good tray support
  - **GNOME:** Tray support is limited; may need extensions
- **pystray:** May not work natively; fallback to waybar or use Qt/GTK for better Wayland support
- **Electron:** Can work via [electron-tray](https://www.electronjs.org/docs/latest/api/tray)

### Windows/macOS
- pystray works out of the box
- No major differences

## 4. Icon Design
- Create two PNG/SVG icons (green and red)
- Place in `logo_ideas/` or a new `icons/` directory
- Use pystray's `Icon` class to set the icon based on status

## 5. Autostart on Login (Optional)
- **Linux:** Create a `.desktop` file in `~/.config/autostart/`
- **Wayland:** Use compositor-specific autostart (e.g., waybar config)
- **Windows:** Add shortcut to Startup folder
- **macOS:** Use Login Items

## 6. Packaging
- Add entry point in `setup.py` (e.g., `signalbox-tray`)
- Document usage in `README.md`

## 7. Troubleshooting
- **Wayland:** If tray icon does not appear, try running under XWayland or use a different tray library (Qt/GTK)
- **Hyprland:** Use waybar for tray support; check documentation for tray modules
- **GNOME:** Install tray extension if needed

## 8. References
[pystray documentation](https://pystray.readthedocs.io/en/latest/)
[Waybar documentation](https://github.com/Alexays/Waybar)
[Hyprland Wiki](https://wiki.hyprland.org/)


## My Recommendation (Linux & macOS)

For best cross-platform support (Linux, macOS):

- **Use Qt (PyQt or PySide)** for the tray app. Qt provides robust tray support on X11, Wayland (via StatusNotifierItem), and macOS, with minimal platform-specific code.
- **Fallback:** If you prefer a pure Python solution, use pystray for simple cases, but expect limited Wayland support and possible issues on some compositors (e.g., Hyprland, GNOME).
- **Icon logic:** Implement green/red status icons as described above.
- **Autostart:** Use .desktop files for Linux and Login Items for macOS.
- **Test on multiple compositors/bars** (Waybar, Sway, Hyprland, GNOME, KDE) to ensure compatibility.

Qt is the most reliable choice for a professional, cross-platform tray experience. pystray is suitable for quick prototypes or personal use, but may require troubleshooting on modern Wayland setups.

## Tray Enable/Disable Option

Add an option to the global config (signalbox.yaml) to enable or disable the tray icon:

```yaml
tray:
  enabled: true
```

Check this value before launching the tray app. This allows users to disable the tray in headless or minimal environments, or when tray support is not desired. Document this option in your config guide and ensure the tray script respects it.
