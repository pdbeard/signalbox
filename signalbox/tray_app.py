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
from pathlib import Path

try:
    from PyQt6.QtCore import QTimer, Qt
    from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
    from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon
except ImportError:
    sys.stderr.write(
        "Signalbox tray requires PyQt6, which is not installed.\n"
        "Install it with: pip install 'signalbox[tray]'  (or: pipx install 'signalbox[tray]')\n"
    )
    raise SystemExit(1)

from .config import find_config_home, get_config_value
from .log_manager import get_latest_log
from .notifications import send_notification
from .runtime import load_tray_state, save_tray_state, set_tray_setting, setting_with_tray_override
from .tray_status import read_status
from .validator import _invalid_whole_number

ICON_DIR = Path(__file__).parent / "icons"
# The tray's Notifications switch mutes both kinds of desktop notification the CLI sends
NOTIFICATION_SETTINGS = ("alerts.notifications.enabled", "group_notifications.enabled")
# Menu row colours, matching the tray icon tiles; grey is for "never run" and skipped on purpose
TILE_COLOURS = {"green": "#22C55E", "yellow": "#EAB308", "red": "#EF4444", "grey": "#94A3B8"}
STATUS_TILES = {"success": "green", "failed": "red", "partial": "red", "alert": "red", "overdue": "yellow"}
_tiles = {}


def _tile(colour):
    """A small rounded square in a status colour, for a menu row."""
    if colour not in _tiles:
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(TILE_COLOURS[colour]))
        painter.drawRoundedRect(4, 4, 24, 24, 6, 6)
        painter.end()
        _tiles[colour] = QIcon(pixmap)
    return _tiles[colour]


def _shorten(text, limit=50):
    """One menu line: long alert messages are cut, so the menu does not get very wide."""
    return text if len(text) <= limit else text[: limit - 1] + "…"


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
        self.overdue_seen = set()

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
            self.status = read_status()
        except Exception as e:
            # e.g. a config file saved half-way: keep the menu, but never stay green while blind
            self.tray.setIcon(QIcon(str(ICON_DIR / "yellow.png")))
            self.tray.setToolTip(f"signalbox: cannot read the state: {e}")
            if self.verbose:
                print(f"[tray] refresh failed: {e}", file=sys.stderr)
            return
        self.tray.setIcon(QIcon(str(ICON_DIR / f"{self.status['colour']}.png")))
        self.tray.setToolTip(self.status["tooltip"])
        self._notify_new_overdue()
        self.menu = self._build_menu(self.status)
        self.tray.setContextMenu(self.menu)
        if self.verbose:
            print(f"[tray] {self.status['colour']}: {self.status['tooltip']}")

    def _notify_new_overdue(self):
        """Notify once when a group becomes overdue: a run that never started sends no other notification."""
        overdue = {name for _, name, _, row_status in self.status["groups"] if row_status == "overdue"}
        new = sorted(overdue - self.overdue_seen)
        self.overdue_seen = overdue  # a group that recovers and is late again notifies again
        if new and setting_with_tray_override("group_notifications.enabled", True):
            send_notification("signalbox: group overdue", f"Did not run when due: {', '.join(new)}")

    def _build_menu(self, status):
        """Summary, then what needs attention, then each group with its tasks in a submenu, then actions."""
        menu = QMenu()
        attention = {name: colour for colour, name, _ in status["attention"]}
        task_names = {row[1] for row in status["tasks"] if row[3] != "never"}

        def add_row(parent, colour, name, detail):
            """One row with a coloured tile; a task that ran opens its latest log when clicked."""
            action = QAction(_tile(colour), f"{name}  ·  {detail}" if detail else name, parent)
            if name in task_names:
                action.triggered.connect(lambda _checked, n=name: self._open_latest_log(n))
            else:
                action.setEnabled(False)
            parent.addAction(action)

        def add_task_row(parent, row):
            _, name, detail, row_status = row
            add_row(parent, attention.get(name) or STATUS_TILES.get(row_status, "grey"), name, detail)

        summary = QAction(f"signalbox: {status['summary']}", menu)
        summary.setEnabled(False)
        menu.addAction(summary)

        if status["attention"]:
            menu.addSection("Needs attention")
            for colour, name, reason in status["attention"]:
                add_row(menu, colour, name, _shorten(reason))

        if status["groups"]:
            menu.addSection("Groups")
            for row in status["groups"]:
                _, name, detail, row_status = row
                colour = attention.get(name) or STATUS_TILES.get(row_status, "grey")
                # a group shows the worst colour of its tasks too, so the problem is easy to find
                member_colours = {attention.get(task_row[1]) for task_row in status["group_tasks"].get(name, [])}
                colour = next((c for c in ("red", "yellow") if c in member_colours | {colour}), colour)
                submenu = menu.addMenu(_tile(colour), f"{name}  ·  {detail}")
                for task_row in status["group_tasks"].get(name, []):
                    add_task_row(submenu, task_row)
                if submenu.isEmpty():
                    submenu.addAction("No tasks").setEnabled(False)
            if status["other_tasks"]:
                others = menu.addMenu(_tile("grey"), "Other tasks")
                for task_row in status["other_tasks"]:
                    add_task_row(others, task_row)
        else:
            menu.addSection("Tasks")
            for task_row in status["other_tasks"] or [("", "No tasks configured", "", "never")]:
                add_task_row(menu, task_row)

        menu.addSeparator()
        # One item: "seen" when there is something to hide, else "unseen" to undo the last "seen"
        if status["can_mark_seen"] or not status.get("can_mark_unseen"):
            seen = QAction("Mark all as seen", menu)
            seen.setEnabled(status["can_mark_seen"])
            seen.triggered.connect(self._mark_seen)
        else:
            seen = QAction("Mark all as unseen", menu)
            seen.triggered.connect(self._mark_unseen)
        menu.addAction(seen)
        notifications = QAction("Notifications", menu)
        notifications.setCheckable(True)
        notifications.setChecked(bool(setting_with_tray_override(NOTIFICATION_SETTINGS[0], True)))
        notifications.toggled.connect(self._set_notifications)
        menu.addAction(notifications)
        for label, handler in (
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

    def _mark_seen(self):
        """Stop counting failures and alerts from runs before now (overdue groups still show)."""
        state = load_tray_state()
        state["seen_previous"] = state.get("ignore_failures_before", 0)  # so "Mark all as unseen" can undo it
        state["ignore_failures_before"] = int(time.time())
        save_tray_state(state)
        self.refresh()

    def _mark_unseen(self):
        """Undo the last "Mark all as seen": the failures and alerts it hid count again."""
        state = load_tray_state()
        state["ignore_failures_before"] = state.pop("seen_previous", 0)
        save_tray_state(state)
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
