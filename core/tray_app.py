"""
Signalbox System Tray Application

Provides a system tray icon with status indication and menu for controlling Signalbox.
"""
import sys
import os
import argparse
import shutil
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtCore import QTimer

from .config import load_config, get_config_value
from .runtime import load_runtime_state
from .exceptions import SignalboxError


class SignalboxTray:
    """System tray application for Signalbox."""

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        if self.verbose:
            print("[VERBOSE] Initializing Signalbox Tray...")
        
        # Load configuration
        try:
            self.config = load_config()
            if self.verbose:
                print(f"[VERBOSE] Configuration loaded successfully")
        except Exception as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Check if tray is enabled
        tray_enabled = get_config_value("tray.enabled", True)
        if self.verbose:
            print(f"[VERBOSE] Tray enabled: {tray_enabled}")
        if not tray_enabled:
            print("Tray is disabled in configuration")
            sys.exit(0)
        
        # Create tray icon
        self.tray_icon = QSystemTrayIcon(self.app)
        self.setup_icon()
        self.setup_menu()
        
        # Set up timer to poll status
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        poll_interval = get_config_value("tray.poll_interval", 30) * 1000  # Convert to ms
        if self.verbose:
            print(f"[VERBOSE] Setting poll interval to {poll_interval/1000} seconds")
        self.timer.start(poll_interval)
        
        # Initial status update
        self.update_status()
        
        # Show tray icon
        self.tray_icon.show()
        if self.verbose:
            print("[VERBOSE] Tray icon shown successfully")

    def setup_icon(self):
        """Set up the tray icon."""
        icon_path = self.get_icon_path("green")
        if self.verbose:
            if icon_path is None:
                print(f"[VERBOSE] Icon path could not be resolved (None). Expected icons directory: {Path(__file__).parent.parent / 'icons'}")
            else:
                print(f"[VERBOSE] Looking for icon at: {icon_path} (exists: {icon_path.exists()})")
        if icon_path and icon_path.exists():
            self.tray_icon.setIcon(QIcon(str(icon_path)))
            if self.verbose:
                print(f"[VERBOSE] Loaded icon from {icon_path}")
        else:
            # Use default system icon as fallback
            self.tray_icon.setIcon(self.app.style().standardIcon(
                self.app.style().StandardPixmap.SP_ComputerIcon
            ))
            if self.verbose:
                print(f"[VERBOSE] Using default system icon (icon file not found)")

    def setup_menu(self):
        """Set up the tray menu."""
        menu = QMenu()
        
        # View Status action
        status_action = QAction("View Status", self.app)
        status_action.triggered.connect(self.show_status)
        menu.addAction(status_action)
        
        menu.addSeparator()
        
        # Run All Tasks action
        run_all_action = QAction("Run All Tasks", self.app)
        run_all_action.triggered.connect(self.run_all_tasks)
        menu.addAction(run_all_action)
        
        menu.addSeparator()
        
        # Open Config action
        config_action = QAction("Open Config", self.app)
        config_action.triggered.connect(self.open_config)
        menu.addAction(config_action)
        
        menu.addSeparator()
        
        # Exit action
        exit_action = QAction("Exit", self.app)
        exit_action.triggered.connect(self.exit_app)
        menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(menu)

    def get_icon_path(self, status):
        """
        Get the path to the icon file based on status.
        
        Args:
            status: 'green' for success, 'red' for failure
        
        Returns:
            Path object or None
        """
        # Try workspace/project directory first
        workspace_icons = Path.cwd() / "icons" / f"{status}.png"
        if workspace_icons.exists():
            return workspace_icons
        # Fallback to package directory
        package_icons = Path(__file__).parent.parent / "icons" / f"{status}.png"
        return package_icons

    def update_status(self):
        """
        Poll runtime state and update icon based on overall status.
        
        Green = all recent tasks successful
        Red = one or more tasks failed
        """
        try:
            runtime_state = load_runtime_state()
            
            # Check if any tasks have failed
            has_failures = False
            task_count = 0
            success_count = 0
            
            if "tasks" in runtime_state:
                for task_name, task_data in runtime_state["tasks"].items():
                    task_count += 1
                    if task_data.get("status") == "failed":
                        has_failures = True
                    elif task_data.get("status") == "success":
                        success_count += 1
            
            if self.verbose:
                print(f"[VERBOSE] Status update: {success_count}/{task_count} tasks successful, failures: {has_failures}")
            
            # Update icon based on status
            if has_failures:
                icon_path = self.get_icon_path("red")
                tooltip = f"Signalbox - {task_count - success_count} task(s) failed"
            elif task_count > 0:
                icon_path = self.get_icon_path("green")
                tooltip = f"Signalbox - All tasks successful ({success_count})"
            else:
                icon_path = self.get_icon_path("green")
                tooltip = "Signalbox - No tasks run yet"
            
            # Update icon if we have one
            if icon_path and icon_path.exists():
                self.tray_icon.setIcon(QIcon(str(icon_path)))
            
            # Update tooltip
            self.tray_icon.setToolTip(tooltip)
            
        except Exception as e:
            error_msg = f"Signalbox - Error: {str(e)}"
            self.tray_icon.setToolTip(error_msg)
            if self.verbose:
                print(f"[VERBOSE] Error updating status: {e}", file=sys.stderr)

    def find_terminal(self):
        """Find an available terminal emulator."""
        terminals = [
            "x-terminal-emulator",
            "gnome-terminal",
            "konsole",
            "xfce4-terminal",
            "xterm",
            "alacritty",
            "kitty",
            "terminator",
        ]
        for term in terminals:
            if shutil.which(term):
                if self.verbose:
                    print(f"[VERBOSE] Found terminal: {term}")
                return term
        if self.verbose:
            print("[VERBOSE] No terminal emulator found", file=sys.stderr)
        return None

    def show_status(self):
        """Show status information (currently opens terminal with signalbox task list)."""
        import subprocess
        terminal = self.find_terminal()
        if not terminal:
            error_msg = "No terminal emulator found. Tried: x-terminal-emulator, gnome-terminal, konsole, xfce4-terminal, xterm, alacritty, kitty, terminator"
            self.tray_icon.showMessage("Error", error_msg)
            if self.verbose:
                print(f"[VERBOSE] {error_msg}", file=sys.stderr)
            return
        
        try:
            if self.verbose:
                print(f"[VERBOSE] Opening terminal: {terminal} -e signalbox task list")
            # Handle different terminal command formats
            if terminal in ["gnome-terminal", "xfce4-terminal"]:
                subprocess.Popen([terminal, "--", "signalbox", "task", "list"])
            else:
                subprocess.Popen([terminal, "-e", "signalbox", "task", "list"])
        except Exception as e:
            error_msg = f"Could not open terminal: {e}"
            self.tray_icon.showMessage("Error", error_msg)
            if self.verbose:
                print(f"[VERBOSE] {error_msg}", file=sys.stderr)

    def run_all_tasks(self):
        """Run all tasks."""
        import subprocess
        terminal = self.find_terminal()
        if not terminal:
            error_msg = "No terminal emulator found"
            self.tray_icon.showMessage("Error", error_msg)
            if self.verbose:
                print(f"[VERBOSE] {error_msg}", file=sys.stderr)
            return
        
        try:
            if self.verbose:
                print(f"[VERBOSE] Running tasks in terminal: {terminal}")
            # Handle different terminal command formats
            if terminal in ["gnome-terminal", "xfce4-terminal"]:
                subprocess.Popen([terminal, "--", "signalbox", "task", "run", "--all"])
            else:
                subprocess.Popen([terminal, "-e", "signalbox", "task", "run", "--all"])
            self.tray_icon.showMessage("Signalbox", "Running all tasks...")
        except Exception as e:
            error_msg = f"Could not run tasks: {e}"
            self.tray_icon.showMessage("Error", error_msg)
            if self.verbose:
                print(f"[VERBOSE] {error_msg}", file=sys.stderr)

    def open_config(self):
        """Open config file in default editor."""
        import subprocess
        config_path = self.config.get("config_file", "config/signalbox.yaml")
        if self.verbose:
            print(f"[VERBOSE] Opening config file: {config_path}")
        try:
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
        """Start the tray application event loop."""
        return self.app.exec()


def main():
    """Entry point for the tray application."""
    import signal
    parser = argparse.ArgumentParser(description="Signalbox System Tray Application")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable verbose output for troubleshooting")
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
