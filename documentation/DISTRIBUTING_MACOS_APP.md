# Distributing a macOS .app Wrapper for signalbox-tray

## Overview
This document describes how to provide a macOS .app bundle that launches the `signalbox-tray` command-line tool, and how users can install it alongside a pipx-installed CLI.

## Why a .app Bundle?
- macOS "Open at Login" and Dock integration work best with .app bundles.
- Running a shell script or .command file at login opens a Terminal window, which is undesirable for background tray apps.
- A .app bundle can run your CLI in the background, with no visible Terminal window.

## Distribution Strategy
1. **Include the .app bundle in your Python package** (e.g., in a `resources/` or `macos/` directory).
2. **Provide a CLI command** (e.g., `signalbox install-app`) that copies the .app to `~/Applications` or another user-specified location.
3. **Document the process** so users know how to install and use the .app after installing your CLI with pipx.

## Example Workflow
1. User runs: `pipx install signalbox`
2. User runs: `signalbox install-app`
   - This copies the prebuilt `SignalboxTray.app` to `~/Applications` (or another location).
3. User adds `SignalboxTray.app` to their login items or Dock.

## Creating the .app Bundle
- Use Automator or AppleScript to create an app that runs the `signalbox-tray` command.
- The app should simply execute `signalbox-tray` (which will be on PATH after pipx install).
- The .app does not need to change unless the command name or behavior changes.

## Example: AppleScript App
1. Open Script Editor and enter:
   ```applescript
   do shell script "/usr/local/bin/signalbox-tray &> /dev/null &"
   ```
   (Adjust the path if needed; `/usr/local/bin` is typical for pipx.)
2. Save as Application: `SignalboxTray.app`
3. Add to your package's resources.

## Installing the .app via CLI
- Add a command to your CLI (e.g., `signalbox install-app`) that copies the .app from your package resources to the user's Applications folder.
- Example (Python):
   ```python
   import shutil
   import os
   import click

   @click.command()
   def install_app():
       src = os.path.join(os.path.dirname(__file__), 'resources', 'SignalboxTray.app')
       dest = os.path.expanduser('~/Applications/SignalboxTray.app')
       shutil.copytree(src, dest, dirs_exist_ok=True)
       click.echo(f"Installed SignalboxTray.app to {dest}")
   ```

## Notes
- The .app must be executable and codesigned if you want to avoid Gatekeeper warnings.
- Users may need to grant permissions the first time they run the app.
- Document any requirements or troubleshooting steps in your README.

---

This approach provides a seamless, native-feeling experience for macOS users running your tray app via pipx.