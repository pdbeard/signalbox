#!/usr/bin/env python3
"""Render the tray icons (signalbox/icons/*.png) from their sources in logo/.

The tray picks the icon by the status colour, so the file names are fixed:
logo/tray-icon-ok.svg -> green.png, tray-icon-overdue.svg -> yellow.png,
tray-icon-failed.svg -> red.png. Needs rsvg-convert (librsvg: `brew install librsvg`
or `apt install librsvg2-bin`). Run it from the repository root after editing an SVG.
"""
import shutil
import subprocess
import sys

SIZE = 128  # px; the tray scales down, and 128 stays sharp on high-DPI screens
ICONS = {"ok": "green", "overdue": "yellow", "failed": "red"}

if __name__ == "__main__":
    if not shutil.which("rsvg-convert"):
        sys.exit("rsvg-convert not found: install librsvg (brew install librsvg / apt install librsvg2-bin)")
    for state, colour in ICONS.items():
        source, target = f"logo/tray-icon-{state}.svg", f"signalbox/icons/{colour}.png"
        subprocess.run(["rsvg-convert", "-w", str(SIZE), "-h", str(SIZE), source, "-o", target], check=True)
        print(f"{source} -> {target}")
