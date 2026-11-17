"""Signalbox tray icon: a read-only status monitor.

The tray never runs tasks. cron/systemd run them and the CLI records each run in
runtime/; every tray.poll_interval seconds the tray reads that state again and
shows it (see tray_status.compute_status for what each colour means).
"""

import argparse
import os
import platform
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QAction, QIcon
    from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
except ImportError:
    sys.stderr.write(
        "Signalbox tray requires PyQt6, which is not installed.\n"
        "Install it with: pip install 'signalbox[tray]'  (or: pipx install 'signalbox[tray]')\n"
    )
    raise SystemExit(1)

from .config import find_config_home, get_config_value, load_config
from .log_manager import get_latest_log
from .runtime import (
    filter_runtime_to_config,
    load_runtime_state,
    load_tray_state,
    set_tray_setting,
    setting_with_tray_override,
)
from .tray_status import compute_status
from .validator import _invalid_whole_number

ICON_DIR = Path(__file__).parent / "icons"
# The tray's Notifications switch mutes both kinds of desktop notification the CLI sends
NOTIFICATION_SETTINGS = ("alerts.notifications.enabled", "group_notifications.enabled")


def _open(path):
    """Open a file or folder with the desktop's default application."""
    subprocess.Popen(["open" if platform.system() == "Darwin" else "xdg-open", path])


class SignalboxTray:
    """The tray icon and its menu, rebuilt from the runtime state on every poll."""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        self.tray = QSystemTrayIcon(self.app)
        self.tray.setIcon(QIcon(str(ICON_DIR / "green.png")))
        self.menu = None
        self.status = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        poll_interval = get_config_value("tray.poll_interval", 30)
        if _invalid_whole_number(poll_interval, minimum=1):
            print(f"tray.poll_interval must be a whole number >= 1, got {poll_interval!r}; using 30", file=sys.stderr)
            poll_interval = 30
        self.timer.start(poll_interval * 1000)
        self.refresh()
        self.tray.show()

    def refresh(self):
        """Read the state once and update the icon, tooltip and menu."""
        if self.menu is not None and self.menu.isVisible():
            return  # rebuilding would close it under the user; aboutToHide refreshes instead
        try:
            config = load_config(suppress_warnings=True)
            runtime_state = filter_runtime_to_config(load_runtime_state(), config)
            ignore_before = load_tray_state().get("ignore_failures_before", 0)
            self.status = compute_status(config, runtime_state, ignore_before, datetime.now())
        except Exception as e:
            # e.g. a config file saved half-way: keep the menu, but never stay green while blind
            self.tray.setIcon(QIcon(str(ICON_DIR / "yellow.png")))
            self.tray.setToolTip(f"signalbox: cannot read the state: {e}")
            if self.verbose:
                print(f"[tray] refresh failed: {e}", file=sys.stderr)
            return
        self.tray.setIcon(QIcon(str(ICON_DIR / f"{self.status['colour']}.png")))
        self.tray.setToolTip(self.status["tooltip"])
        self.menu = self._build_menu(self.status)
        self.tray.setContextMenu(self.menu)
        if self.verbose:
            print(f"[tray] {self.status['colour']}: {self.status['tooltip']}")

    def _build_menu(self, status):
        menu = QMenu()
        for title, kind in (("Groups", "groups"), ("Tasks", "tasks")):
            menu.addSection(title)
            rows = status[kind] or [("", f"No {kind} configured", "", "never")]
            for icon, name, detail, row_status in rows:
                action = QAction(f"{icon} {name}  ·  {detail}" if detail else name, menu)
                if kind == "tasks" and row_status != "never":
                    action.triggered.connect(lambda _checked, n=name: self._open_latest_log(n))
                else:
                    action.setEnabled(False)
                menu.addAction(action)

        menu.addSeparator()
        notifications = QAction("Notifications", menu)
        notifications.setCheckable(True)
        notifications.setChecked(bool(setting_with_tray_override(NOTIFICATION_SETTINGS[0], True)))
        notifications.toggled.connect(self._set_notifications)
        menu.addAction(notifications)
        for label, handler in (
            ("Clear error state", self._clear_errors),
            ("Open config folder", lambda: _open(os.path.join(find_config_home(), "config"))),
            ("Quit", self.app.quit),
        ):
            action = QAction(label, menu)
            action.triggered.connect(handler)
            menu.addAction(action)

        # Refresh as soon as the menu closes; the delay lets it finish hiding first
        menu.aboutToHide.connect(lambda: QTimer.singleShot(100, self.refresh))
        return menu

    def _open_latest_log(self, task_name):
        log_path, exists = get_latest_log(task_name)
        if exists:
            _open(log_path)

    def _set_notifications(self, enabled):
        for key in NOTIFICATION_SETTINGS:
            set_tray_setting(key, enabled)

    def _clear_errors(self):
        """Stop counting failures that happened before now (overdue groups still show)."""
        set_tray_setting("ignore_failures_before", int(time.time()))
        self.refresh()

    def run(self):
        return self.app.exec()


def main():
    """Entry point for the signalbox-tray command."""
    parser = argparse.ArgumentParser(description="Signalbox tray icon: shows the status of tasks and groups")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print each status update")
    args = parser.parse_args()

    if not get_config_value("tray.enabled", True):
        print("The tray is disabled (tray.enabled: false in signalbox.yaml)")
        sys.exit(0)
    # Qt's event loop never returns to Python's signal handler, so let Ctrl+C end the process directly
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    sys.exit(SignalboxTray(verbose=args.verbose).run())


if __name__ == "__main__":
    main()
