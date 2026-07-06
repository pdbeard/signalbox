"""
Signalbox System Tray Application

Provides a system tray icon with status indication and menu for controlling Signalbox.
"""

import sys
import os
import re
import argparse
import tempfile
from datetime import datetime
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QApplication,
        QSystemTrayIcon,
        QMenu,
        QDialog,
        QVBoxLayout,
        QLabel,
        QTextEdit,
        QPushButton,
    )
    from PyQt6.QtGui import QIcon, QAction
    from PyQt6.QtCore import QTimer, pyqtSignal, QObject
except ImportError:
    sys.stderr.write(
        "Signalbox tray requires PyQt6, which is not installed.\n"
        "Install it with: pip install 'signalbox[tray]'  (or: pipx install 'signalbox[tray]')\n"
    )
    raise SystemExit(1)

from .config import load_config, get_config_value, find_config_home, save_global_config_value
from .runtime import load_runtime_state

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _parse_last_run_to_ts(last_run):
    """Parse a last_run value to a Unix timestamp int. Returns 0 on failure."""
    if isinstance(last_run, (int, float)):
        return int(last_run)
    if not last_run or last_run == "Never":
        return 0
    m = re.match(r"(\d{8})_(\d{6})_\d+", str(last_run))
    if m:
        date_str, time_str = m.group(1), m.group(2)
        try:
            dt = datetime.strptime(date_str + time_str, "%Y%m%d%H%M%S")
            return int(dt.timestamp())
        except Exception:
            return 0
    try:
        dt = datetime.fromisoformat(str(last_run))
        return int(dt.timestamp())
    except Exception:
        return 0


def _human_delta(ts):
    """Return a human-readable string for how long ago a timestamp was."""
    if not ts:
        return "never"
    delta = int(datetime.now().timestamp()) - ts
    if delta < 60:
        return f"{delta} sec"
    elif delta < 3600:
        return f"{round(delta / 60)} min"
    elif delta < 86400:
        return f"{round(delta / 3600)} hr"
    else:
        days = round(delta / 86400)
        return f"{days} day" if days == 1 else f"{days} days"


def _load_tray_state():
    """Load tray-specific state (ignore_failures_before) from the state file."""
    import json

    state_file = os.path.expanduser("~/.signalbox_tray_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_tray_state(state):
    """Save tray-specific state atomically to the state file."""
    import json

    state_file = os.path.expanduser("~/.signalbox_tray_state.json")
    state_dir = os.path.dirname(state_file)
    fd, tmp_path = tempfile.mkstemp(dir=state_dir, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        os.replace(tmp_path, state_file)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Qt classes
# ---------------------------------------------------------------------------


class WorkerSignals(QObject):
    """Signals for thread-safe communication from background threads to Qt main thread."""

    finished = pyqtSignal(bool)  # Success status
    status_update = pyqtSignal()  # Trigger status update
    show_message = pyqtSignal(str, str)  # Title, message


class StatusDialog(QDialog):
    """Dialog window to display task status."""

    def __init__(self, runtime_state, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Signalbox Status")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        layout = QVBoxLayout()

        task_count = 0
        success_count = 0
        failed_count = 0
        failed_tasks = []

        if "tasks" in runtime_state:
            for task_name, task_data in runtime_state["tasks"].items():
                task_count += 1
                last_status = task_data.get("last_status", "unknown")
                if last_status == "success":
                    success_count += 1
                elif last_status == "failed":
                    failed_count += 1
                    failed_tasks.append(task_name)

        summary = f"Tasks: {task_count} total, {success_count} successful, {failed_count} failed"
        summary_label = QLabel(summary)
        summary_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 10px;")
        layout.addWidget(summary_label)

        status_text = QTextEdit()
        status_text.setReadOnly(True)

        text_content = ["TASK STATUS\n" + "=" * 60 + "\n"]

        if "tasks" in runtime_state and runtime_state["tasks"]:
            for task_name, task_data in sorted(runtime_state["tasks"].items()):
                last_run = task_data.get("last_run", "Never")
                last_status = task_data.get("last_status", "unknown")
                status_icon = "✓" if last_status == "success" else "✗" if last_status == "failed" else "?"
                text_content.append(f"{status_icon} {task_name}")
                text_content.append(f"  Status: {last_status}")
                text_content.append(f"  Last Run: {last_run}\n")
        else:
            text_content.append("No tasks have been run yet.\n")

        if "groups" in runtime_state and runtime_state["groups"]:
            text_content.append("\nGROUP STATUS\n" + "=" * 60 + "\n")
            for group_name, group_data in sorted(runtime_state["groups"].items()):
                last_run = group_data.get("last_run", "Never")
                last_status = group_data.get("last_status", "unknown")
                tasks_total = group_data.get("tasks_total", 0)
                tasks_successful = group_data.get("tasks_successful", 0)
                success_rate = group_data.get("success_rate", 0)
                status_icon = "✓" if last_status == "success" else "✗" if last_status == "failed" else "?"
                text_content.append(f"{status_icon} {group_name}")
                text_content.append(f"  Status: {last_status}")
                text_content.append(f"  Last Run: {last_run}")
                text_content.append(f"  Tasks: {tasks_successful}/{tasks_total} ({success_rate}%)\n")

        status_text.setPlainText("\n".join(text_content))
        layout.addWidget(status_text)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.setLayout(layout)


class SignalboxTray:
    """System tray application for Signalbox."""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self._is_loading = False
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        self.signals = WorkerSignals()
        self.signals.finished.connect(self._on_task_finished)
        self.signals.status_update.connect(self.update_status)
        self.signals.show_message.connect(lambda title, msg: self.tray_icon.showMessage(title, msg))

        if self.verbose:
            print("[VERBOSE] Initializing Signalbox Tray...")

        try:
            self.config = load_config()
            if self.verbose:
                print("[VERBOSE] Configuration loaded successfully")
        except Exception as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            sys.exit(1)

        tray_enabled = get_config_value("tray.enabled", True)
        if self.verbose:
            print(f"[VERBOSE] Tray enabled: {tray_enabled}")
        if not tray_enabled:
            print("Tray is disabled in configuration")
            sys.exit(0)

        self.tray_icon = QSystemTrayIcon(self.app)
        self.setup_icon()
        self.setup_menu()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        poll_interval = get_config_value("tray.poll_interval", 30) * 1000
        if self.verbose:
            print(f"[VERBOSE] Setting poll interval to {poll_interval/1000} seconds")
        self.timer.start(poll_interval)

        self.update_status()
        self.tray_icon.show()
        if self.verbose:
            print("[VERBOSE] Tray icon shown successfully")

    def setup_icon(self):
        """Set up the tray icon."""
        icon_path = self.get_icon_path("green")
        if self.verbose:
            if icon_path is None:
                print(
                    f"[VERBOSE] Icon path could not be resolved (None). Expected icons directory: {Path(__file__).parent.parent / 'icons'}"
                )
            else:
                print(f"[VERBOSE] Looking for icon at: {icon_path} (exists: {icon_path.exists()})")
        if icon_path and icon_path.exists():
            self.tray_icon.setIcon(QIcon(str(icon_path)))
            if self.verbose:
                print(f"[VERBOSE] Loaded icon from {icon_path}")
        else:
            self.tray_icon.setIcon(self.app.style().standardIcon(self.app.style().StandardPixmap.SP_ComputerIcon))
            if self.verbose:
                print("[VERBOSE] Using default system icon (icon file not found)")

    def setup_menu(self):
        """Build (or rebuild) the tray context menu.

        Called once at startup and again on every status poll so that inline
        task/group statuses stay current. Skipped if the menu is currently
        visible to avoid a mid-interaction rebuild.
        """
        current_menu = self.tray_icon.contextMenu() if hasattr(self, "tray_icon") else None
        if current_menu and current_menu.isVisible():
            return

        menu = QMenu()
        runtime_state = load_runtime_state()

        # --- Inline task status ---
        menu.addSection("Task Status")
        if "tasks" in runtime_state:
            for task_name, task_data in sorted(runtime_state["tasks"].items()):
                last_status = task_data.get("last_status", "unknown")
                last_run = task_data.get("last_run", "Never")
                last_run_ts = _parse_last_run_to_ts(last_run)
                status_icon = "✓" if last_status == "success" else "✗" if last_status == "failed" else "?"
                label = f"{status_icon} {task_name} | {_human_delta(last_run_ts)}"
                action = QAction(label, menu)
                action.setEnabled(False)
                menu.addAction(action)
        else:
            no_tasks = QAction("No tasks have been run yet.", menu)
            no_tasks.setEnabled(False)
            menu.addAction(no_tasks)

        # --- Inline group status ---
        menu.addSection("Group Status")
        if "groups" in runtime_state:
            for group_name, group_data in sorted(runtime_state["groups"].items()):
                last_status = group_data.get("last_status", "unknown")
                last_run = group_data.get("last_run", "Never")
                last_run_ts = _parse_last_run_to_ts(last_run)
                status_icon = "✓" if last_status == "success" else "✗" if last_status == "failed" else "?"
                label = f"{status_icon} {group_name} | {_human_delta(last_run_ts)}"
                action = QAction(label, menu)
                action.setEnabled(False)
                menu.addAction(action)
        else:
            no_groups = QAction("No groups have been run yet.", menu)
            no_groups.setEnabled(False)
            menu.addAction(no_groups)

        menu.addSeparator()

        status_action = QAction("View Status", self.app)
        status_action.triggered.connect(self.show_status)
        menu.addAction(status_action)

        menu.addSeparator()

        run_all_action = QAction("Run All Tasks", self.app)
        run_all_action.triggered.connect(self.run_all_tasks)
        menu.addAction(run_all_action)

        menu.addSeparator()

        # --- Run Group submenu ---
        group_menu = QMenu("Run Group", menu)
        config = self.config if hasattr(self, "config") else load_config()
        group_sources = config.get("_group_sources", {})
        groups_by_file = {}
        for group in config.get("groups", []):
            group_name = group.get("name")
            source_file = group_sources.get(group_name, "(unknown)")
            groups_by_file.setdefault(source_file, []).append(group_name)
        for file, group_names in groups_by_file.items():
            file_menu = QMenu(os.path.basename(file), group_menu)
            for group_name in group_names:
                action = QAction(group_name, file_menu)
                action.triggered.connect(lambda checked, name=group_name: self.run_group(name))
                file_menu.addAction(action)
            group_menu.addMenu(file_menu)
        menu.addMenu(group_menu)

        # --- Run Task submenu ---
        task_menu = QMenu("Run Task", menu)
        task_sources = config.get("_task_sources", {})
        tasks_by_file = {}
        for task in config.get("tasks", []):
            task_name = task.get("name")
            source_file = task_sources.get(task_name, "(unknown)")
            tasks_by_file.setdefault(source_file, []).append(task_name)
        for file, task_names in tasks_by_file.items():
            file_menu = QMenu(os.path.basename(file), task_menu)
            for task_name in task_names:
                action = QAction(task_name, file_menu)
                action.triggered.connect(lambda checked, name=task_name: self.run_task(name))
                file_menu.addAction(action)
            task_menu.addMenu(file_menu)
        menu.addMenu(task_menu)

        menu.addSeparator()

        # --- Notification toggles — read from and write to signalbox.yaml ---
        # Changes here are immediately visible to the CLI too.
        notifications_enabled = get_config_value("alerts.notifications.enabled", True)
        notify_failures_only = get_config_value("alerts.notifications.on_failure_only", True)

        notif_toggle = QAction("Enable Notifications", menu)
        notif_toggle.setCheckable(True)
        notif_toggle.setChecked(notifications_enabled)

        def toggle_notifications(checked):
            save_global_config_value("alerts.notifications.enabled", checked)

        notif_toggle.toggled.connect(toggle_notifications)
        menu.addAction(notif_toggle)

        notify_mode_toggle = QAction("Notify on Success & Failure", menu)
        notify_mode_toggle.setCheckable(True)
        # Checked = notify on success AND failure (failures_only is False)
        notify_mode_toggle.setChecked(not notify_failures_only)

        def toggle_notify_mode(checked):
            save_global_config_value("alerts.notifications.on_failure_only", not checked)

        notify_mode_toggle.toggled.connect(toggle_notify_mode)
        menu.addAction(notify_mode_toggle)

        menu.addSeparator()

        clear_error_action = QAction("Clear error state", self.app)
        clear_error_action.triggered.connect(self.clear_error_state)
        menu.addAction(clear_error_action)

        menu.addSeparator()

        config_action = QAction("Open Config", self.app)
        config_action.triggered.connect(self.open_config)
        menu.addAction(config_action)

        menu.addSeparator()

        exit_action = QAction("Exit", self.app)
        exit_action.triggered.connect(self.exit_app)
        menu.addAction(exit_action)

        # When the user dismisses the menu, run a fresh update immediately
        # rather than waiting for the next timer tick. A short delay ensures
        # the menu is fully hidden before update_status checks isVisible().
        menu.aboutToHide.connect(lambda: QTimer.singleShot(100, self.update_status))

        self.tray_icon.setContextMenu(menu)

    def run_group(self, group_name):
        """Run a group by name in a background thread."""
        import subprocess
        import threading

        if self._is_loading:
            self.tray_icon.showMessage("Signalbox", "A task is already running, please wait.")
            return

        def run_group_bg():
            try:
                result = subprocess.run(
                    ["signalbox", "group", "run", group_name],
                    capture_output=True,
                    text=True,
                )
                self.signals.finished.emit(result.returncode == 0)
            except Exception as e:
                self.signals.show_message.emit("Error", f"Could not run group {group_name}: {e}")
                self.signals.finished.emit(False)

        self.set_loading_state(True)
        self.tray_icon.showMessage("Signalbox", f"Running group: {group_name}")
        threading.Thread(target=run_group_bg, daemon=True).start()

    def run_task(self, task_name):
        """Run a task by name in a background thread."""
        import subprocess
        import threading

        if self._is_loading:
            self.tray_icon.showMessage("Signalbox", "A task is already running, please wait.")
            return

        def run_task_bg():
            try:
                result = subprocess.run(
                    ["signalbox", "task", "run", task_name],
                    capture_output=True,
                    text=True,
                )
                self.signals.finished.emit(result.returncode == 0)
            except Exception as e:
                self.signals.show_message.emit("Error", f"Could not run task {task_name}: {e}")
                self.signals.finished.emit(False)

        self.set_loading_state(True)
        self.tray_icon.showMessage("Signalbox", f"Running task: {task_name}")
        threading.Thread(target=run_task_bg, daemon=True).start()

    def run_all_tasks(self):
        """Run all tasks in a background thread."""
        import subprocess
        import threading

        if self._is_loading:
            self.tray_icon.showMessage("Signalbox", "A task is already running, please wait.")
            return

        def run_tasks_background():
            try:
                if self.verbose:
                    print("[VERBOSE] Running all tasks in background...")
                result = subprocess.run(
                    ["signalbox", "task", "run", "--all"],
                    capture_output=True,
                    text=True,
                )
                if self.verbose:
                    print(f"[VERBOSE] Task run completed with return code: {result.returncode}")
                    if result.stdout:
                        print(f"[VERBOSE] stdout: {result.stdout[:500]}")
                    if result.stderr:
                        print(f"[VERBOSE] stderr: {result.stderr[:500]}")
                self.signals.finished.emit(result.returncode == 0)
            except Exception as e:
                error_msg = f"Could not run tasks: {e}"
                if self.verbose:
                    print(f"[VERBOSE] {error_msg}", file=sys.stderr)
                self.signals.show_message.emit("Error", error_msg)
                self.signals.finished.emit(False)

        self.set_loading_state(True)
        self.tray_icon.showMessage("Signalbox", "Running all tasks...")
        threading.Thread(target=run_tasks_background, daemon=True).start()

    def clear_error_state(self):
        """Set a timestamp to ignore failures before now and reset the tray icon to green."""
        import time

        state = _load_tray_state()
        state["ignore_failures_before"] = int(time.time())
        _save_tray_state(state)
        self.tray_icon.showMessage("Signalbox", "Error state cleared. Tray will ignore failures before now.")
        self.update_status()

    def get_icon_path(self, status):
        """Get the path to the icon file for the given status ('green', 'red', 'yellow').

        Returns a Path object. Prefers the development workspace location, then
        falls back to the installed package directory.
        """
        workspace_icons = Path.cwd() / "core" / "icons" / f"{status}.png"
        if workspace_icons.exists():
            return workspace_icons
        return Path(__file__).parent / "icons" / f"{status}.png"

    def update_status(self):
        """Poll runtime state, update the icon/tooltip, and refresh the menu.

        Green  = all recent tasks successful (or none run yet)
        Red    = one or more tasks failed (not ignored by clear_error_state)
        Yellow = a task is currently running (set by set_loading_state)

        Skipped entirely if the menu is open — setIcon/setContextMenu can
        dismiss the menu mid-interaction. setup_menu connects aboutToHide so a
        refresh fires automatically as soon as the user closes the menu.
        """
        if self._is_loading:
            if self.verbose:
                print("[VERBOSE] Skipping status update - loading state active")
            return

        current_menu = self.tray_icon.contextMenu() if hasattr(self, "tray_icon") else None
        if current_menu and current_menu.isVisible():
            if self.verbose:
                print("[VERBOSE] Skipping status update - menu is open")
            return

        ignore_before = _load_tray_state().get("ignore_failures_before", 0)

        try:
            runtime_state = load_runtime_state()

            task_count = 0
            success_count = 0
            failed_count = 0

            if "tasks" in runtime_state:
                for task_name, task_data in runtime_state["tasks"].items():
                    task_count += 1
                    last_status = task_data.get("last_status", "")
                    last_run = task_data.get("last_run_time", None) or task_data.get("last_run", None)
                    last_run_ts = _parse_last_run_to_ts(last_run)
                    if last_status == "failed" and last_run_ts > ignore_before:
                        failed_count += 1
                    elif last_status == "success":
                        success_count += 1

            if self.verbose:
                print(f"[VERBOSE] Status update: {success_count}/{task_count} successful, {failed_count} failed")

            if failed_count > 0:
                icon_path = self.get_icon_path("red")
                tooltip = f"Signalbox - {failed_count} task(s) failed"
            elif task_count > 0:
                icon_path = self.get_icon_path("green")
                tooltip = f"Signalbox - All tasks successful ({success_count})"
            else:
                icon_path = self.get_icon_path("green")
                tooltip = "Signalbox - No tasks run yet"

            if icon_path and icon_path.exists():
                icon = QIcon(str(icon_path))
                if not icon.isNull():
                    self.tray_icon.setIcon(icon)
                    if self.verbose:
                        print(f"[VERBOSE] Updated icon to: {icon_path.name}")
                elif self.verbose:
                    print(f"[VERBOSE] WARNING: Icon is null for {icon_path}")
            elif self.verbose:
                print(f"[VERBOSE] WARNING: Icon not found at {icon_path}")

            self.tray_icon.setToolTip(tooltip)

            # Rebuild the menu so inline task/group statuses are current
            self.setup_menu()

        except Exception as e:
            self.tray_icon.setToolTip(f"Signalbox - Error: {str(e)}")
            if self.verbose:
                print(f"[VERBOSE] Error updating status: {e}", file=sys.stderr)

    def show_status(self):
        """Show the status dialog."""
        try:
            runtime_state = load_runtime_state()
            dialog = StatusDialog(runtime_state, parent=None)
            dialog.exec()
        except Exception as e:
            error_msg = f"Could not load status: {e}"
            self.tray_icon.showMessage("Error", error_msg)
            if self.verbose:
                print(f"[VERBOSE] {error_msg}", file=sys.stderr)

    def set_loading_state(self, loading):
        """Set the loading flag and update the icon to yellow (or clear it)."""
        self._is_loading = loading
        if loading:
            icon_path = self.get_icon_path("yellow")
            if self.verbose:
                print(f"[VERBOSE] Yellow icon path: {icon_path}, exists: {icon_path.exists() if icon_path else 'None'}")
            if icon_path and icon_path.exists():
                icon = QIcon(str(icon_path))
                if not icon.isNull():
                    self.tray_icon.setIcon(icon)
                    self.tray_icon.setToolTip("Signalbox - Running tasks...")
                    if self.verbose:
                        print("[VERBOSE] Set loading state (yellow icon)")
                elif self.verbose:
                    print("[VERBOSE] WARNING: Yellow icon is null, not updating")
            elif self.verbose:
                print("[VERBOSE] WARNING: Yellow icon not found, icon not updated")
        else:
            if self.verbose:
                print("[VERBOSE] Cleared loading state")

    def _on_task_finished(self, success):
        """Callback when a background task finishes. Runs in the main thread via Qt signal."""
        self.set_loading_state(False)

        notifications_enabled = get_config_value("alerts.notifications.enabled", True)
        notify_failures_only = get_config_value("alerts.notifications.on_failure_only", True)

        if notifications_enabled:
            if success and not notify_failures_only:
                self.tray_icon.showMessage("Signalbox", "All tasks completed successfully")
            elif not success:
                self.tray_icon.showMessage("Signalbox", "Some tasks failed - check logs")

        self.update_status()

    def open_config(self):
        """Open signalbox.yaml in the system default editor."""
        import subprocess
        import platform

        config_home = find_config_home()
        config_path = os.path.join(config_home, "config", "signalbox.yaml")
        if self.verbose:
            print(f"[VERBOSE] Opening config file: {config_path}")
        try:
            if platform.system() == "Darwin":
                subprocess.Popen(["open", config_path])
            else:
                subprocess.Popen(["xdg-open", config_path])
        except Exception as e:
            error_msg = f"Could not open config: {e}"
            self.tray_icon.showMessage("Error", error_msg)
            if self.verbose:
                print(f"[VERBOSE] {error_msg}", file=sys.stderr)

    def exit_app(self):
        """Exit the tray application."""
        if self.verbose:
            print("[VERBOSE] Exiting tray application")
        self.tray_icon.hide()
        QApplication.quit()

    def run(self):
        """Start the Qt event loop."""
        return self.app.exec()


def main():
    """Entry point for the tray application."""
    import signal

    parser = argparse.ArgumentParser(description="Signalbox System Tray Application")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output for troubleshooting")
    args = parser.parse_args()

    tray = SignalboxTray(verbose=args.verbose)

    def handle_sigint(signum, frame):
        print("\nExiting via Ctrl+C...")
        tray.exit_app()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        sys.exit(tray.run())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
