#!/bin/bash

# Launcher for signalbox-tray for macOS Login Items
# This script can be added to System Settings > Login Items for autostart

SIGNALBOX_TRAY_PATH="$(command -v signalbox-tray)"
if [ -z "$SIGNALBOX_TRAY_PATH" ]; then
  echo "signalbox-tray not found in PATH. Is it installed?"
  exit 1
fi

"$SIGNALBOX_TRAY_PATH"
