# Export functionality for systemd and cron

import os
from .config import get_config_value


class ExportResult:
    """Container for export operation results."""

    def __init__(self, success=False, files=None, error=None):
        self.success = success
        self.files = files or []
        self.error = error


def validate_group_for_export(group, group_name):
    """Validate that a group can be exported.

    Returns:
            tuple: (is_valid, error_message)
    """
    if not group:
        return False, f"Group '{group_name}' not found"

    if "schedule" not in group:
        return False, f"Group '{group_name}' has no schedule defined. Add a 'schedule' field with a cron expression."

    return True, None


def get_schedule_string(group):
    """Extract schedule string from group config.
    
    Supports both formats:
    - String: schedule: "0 * * * *"
    - Dict: schedule: { cron: "0 * * * *" }
    
    Args:
        group: Group configuration dict
        
    Returns:
        str: Cron schedule string
    """
    schedule = group.get("schedule")
    if isinstance(schedule, dict):
        return schedule.get("cron", "")
    return schedule or ""


def get_python_executable():
    """Determine the Python executable to use for exported tasks.

    Returns:
            str: Path to Python executable
    """
    import sys

    return sys.executable


def get_signalbox_command():
    """Determine the signalbox command to use for exported tasks.

    Returns:
            str: Command to invoke signalbox (either CLI entry point or task path)
    """
    import shutil

    # Check if signalbox is installed as a CLI command
    signalbox_cmd = shutil.which("signalbox")
    if signalbox_cmd:
        return "signalbox"

    # Fall back to development mode - use the root signalbox.py
    # Find the project root (parent of core directory)
    core_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(core_dir)
    signalbox_py = os.path.join(project_root, "signalbox.py")

    if os.path.exists(signalbox_py):
        python_exec = get_python_executable()
        return f"{python_exec} {signalbox_py}"

    # Last resort fallback
    return "signalbox"


def get_task_dir():
    """Get the absolute path to the task directory.

    Returns the directory where tasks should be executed from.
    In production, this is typically the user's home or config directory.
    In development, this is the project root.
    """
    import shutil

    # If signalbox is installed, use the config directory
    if shutil.which("signalbox"):
        return os.path.expanduser("~/.config/signalbox")

    # In development mode, use project root
    core_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(core_dir)
    return project_root


def generate_systemd_service(group, group_name):
    """Generate systemd service file content.

    Args:
            group: Group configuration dict
            group_name: Name of the group

    Returns:
            str: Service file content
    """
    task_dir = get_task_dir()
    signalbox_cmd = get_signalbox_command()

    return f"""[Unit]
Description=signalbox - {group.get('description', group_name)}
After=network.target

[Service]
Type=oneshot
WorkingDirectory={task_dir}
ExecStart={signalbox_cmd} run-group {group_name}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""


def generate_systemd_timer(group, group_name):
    """Generate systemd timer file content.

    Args:
            group: Group configuration dict
            group_name: Name of the group

    Returns:
            str: Timer file content
    """
    service_name = f"signalbox-{group_name}"
    cron_schedule = get_schedule_string(group)

    return f"""[Unit]
Description=Timer for signalbox - {group.get('description', group_name)}
Requires={service_name}.service

[Timer]
# Cron schedule: {cron_schedule}
OnCalendar=*-*-* *:00:00
# For custom timing, edit the OnCalendar line above
# Examples:
#   Every 5 minutes: *:0/5
#   Hourly: hourly
#   Daily at 2 AM: 02:00
#   See: man systemd.time

[Install]
WantedBy=timers.target
"""


def export_systemd(group, group_name):
    """Export systemd service and timer files for a group.

    Args:
            group: Group configuration dict
            group_name: Name of the group

    Returns:
            ExportResult: Result of the export operation
    """
    # Validate group
    is_valid, error = validate_group_for_export(group, group_name)
    if not is_valid:
        return ExportResult(success=False, error=error)

    # Create export directory
    export_base_dir = get_config_value("paths.systemd_export_dir", "systemd")
    export_dir = os.path.join(export_base_dir, group_name)
    os.makedirs(export_dir, exist_ok=True)

    service_name = f"signalbox-{group_name}"
    service_file = os.path.join(export_dir, f"{service_name}.service")
    timer_file = os.path.join(export_dir, f"{service_name}.timer")

    # Generate and write service file
    service_content = generate_systemd_service(group, group_name)
    with open(service_file, "w") as f:
        f.write(service_content)

    # Generate and write timer file
    timer_content = generate_systemd_timer(group, group_name)
    with open(timer_file, "w") as f:
        f.write(timer_content)

    return ExportResult(success=True, files=[service_file, timer_file])


def get_systemd_install_instructions(service_file, timer_file, group_name, user=False):
    """Get installation instructions for systemd files.

    Returns:
            list: List of instruction strings
    """
    service_name = f"signalbox-{group_name}"
    instructions = []

    if user:
        install_path = "~/.config/systemd/user/"
        instructions.extend(
            [
                "To install (user mode):",
                f"  mkdir -p {install_path}",
                f"  cp {service_file} {timer_file} {install_path}",
                f"  systemctl --user daemon-reload",
                f"  systemctl --user enable {service_name}.timer",
                f"  systemctl --user start {service_name}.timer",
                "",
                "To check status:",
                f"  systemctl --user status {service_name}.timer",
            ]
        )
    else:
        instructions.extend(
            [
                "To install (requires root):",
                f"  sudo cp {service_file} {timer_file} /etc/systemd/system/",
                f"  sudo systemctl daemon-reload",
                f"  sudo systemctl enable {service_name}.timer",
                f"  sudo systemctl start {service_name}.timer",
                "",
                "To check status:",
                f"  sudo systemctl status {service_name}.timer",
            ]
        )

    return instructions


def generate_cron_entry(group, group_name):
    """Generate cron entry for a group.

    Args:
            group: Group configuration dict
            group_name: Name of the group

    Returns:
            str: Cron entry line
    """
    task_dir = get_task_dir()
    signalbox_cmd = get_signalbox_command()

    return f"{get_schedule_string(group)} cd {task_dir} && {signalbox_cmd} run-group {group_name}"


def export_cron(group, group_name):
    """Export crontab entry for a group.

    Args:
            group: Group configuration dict
            group_name: Name of the group

    Returns:
            ExportResult: Result of the export operation with cron_entry attribute
    """
    # Validate group
    is_valid, error = validate_group_for_export(group, group_name)
    if not is_valid:
        return ExportResult(success=False, error=error)

    # Create export directory
    export_base_dir = get_config_value("paths.cron_export_dir", "cron")
    export_dir = os.path.join(export_base_dir, group_name)
    os.makedirs(export_dir, exist_ok=True)

    cron_file = os.path.join(export_dir, f"{group_name}.cron")
    cron_entry = generate_cron_entry(group, group_name)

    # Write to file
    with open(cron_file, "w") as f:
        f.write(f"# {group.get('description', group_name)}\n")
        f.write(f"{cron_entry}\n")

    result = ExportResult(success=True, files=[cron_file])
    result.cron_entry = cron_entry

    return result


def get_cron_install_instructions(cron_file, cron_entry, group):
    """Get installation instructions for cron entry.

    Returns:
            list: List of instruction strings
    """
    return [
        "Crontab entry:",
        f"# {group.get('description', '')}",
        cron_entry,
        "",
        "To install:",
        "  crontab -e",
        "Then add the line above to your crontab, or:",
        "  crontab -l > /tmp/mycron",
        f"  cat {cron_file} >> /tmp/mycron",
        "  crontab /tmp/mycron",
    ]
