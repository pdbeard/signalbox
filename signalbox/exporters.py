# Export functionality for systemd and cron

import os
import shlex
import shutil
import sys

from .config import get_config_value, find_config_home, resolve_path

CRON_MACROS = {
    "@hourly": "hourly",
    "@daily": "daily",
    "@midnight": "daily",
    "@weekly": "weekly",
    "@monthly": "monthly",
    "@yearly": "yearly",
    "@annually": "yearly",
}
WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


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
    return sys.executable


def get_signalbox_command():
    """Determine the absolute command used to invoke signalbox from cron/systemd.

    Both run with a minimal PATH (pipx installs to ~/.local/bin, which cron
    does not search), and systemd requires an absolute ExecStart path, so the
    resolved path is used rather than a bare "signalbox".

    Returns:
            str: Shell-quoted command to invoke signalbox
    """
    signalbox_cmd = shutil.which("signalbox")
    if signalbox_cmd:
        return shlex.quote(os.path.abspath(signalbox_cmd))

    # Not on PATH (e.g. running from a source checkout): run the package module
    return f"{shlex.quote(get_python_executable())} -m signalbox"


def get_task_dir():
    """Get the absolute path of the signalbox home that exported jobs should use.

    This is the same directory the current CLI invocation resolved, so
    SIGNALBOX_HOME, XDG_CONFIG_HOME and --config are honoured.
    """
    return os.path.abspath(find_config_home())


def _convert_cron_field(value, field, start):
    """Convert one numeric cron field to systemd calendar syntax.

    Args:
        value: Cron field text, e.g. "*", "*/5", "1-5", "0,30"
        field: Field name, used in error messages
        start: First value of the field, used for "*/N" (0 for minute/hour, 1 for day/month)
    """
    parts = []
    for item in value.split(","):
        if item == "*":
            parts.append("*")
        elif item.startswith("*/") and item[2:].isdigit():
            parts.append(f"{start}/{item[2:]}")
        elif "-" in item and "/" not in item:
            low, high = item.split("-", 1)
            if not (low.isdigit() and high.isdigit()):
                raise ValueError(f"unsupported {field} field '{value}'")
            parts.append(f"{low}..{high}")
        elif "/" in item and "-" not in item:
            base, step = item.split("/", 1)
            if not (base.isdigit() and step.isdigit()):
                raise ValueError(f"unsupported {field} field '{value}'")
            parts.append(item)
        elif item.isdigit():
            parts.append(item)
        else:
            raise ValueError(f"unsupported {field} field '{value}'")
    return ",".join(parts)


def _convert_cron_weekday(value):
    """Convert a cron day-of-week field to systemd syntax ('' means any day)."""
    if value == "*":
        return ""

    def name(day):
        if day.isdigit() and 0 <= int(day) <= 7:
            return WEEKDAYS[int(day)]
        if day[:3].capitalize() in WEEKDAYS:
            return day[:3].capitalize()
        raise ValueError(f"unsupported day-of-week field '{value}'")

    parts = []
    for item in value.split(","):
        if "/" in item:
            raise ValueError(f"unsupported day-of-week field '{value}'")
        if "-" in item:
            low, high = item.split("-", 1)
            parts.append(f"{name(low)}..{name(high)}")
        else:
            parts.append(name(item))
    return ",".join(parts)


def cron_to_oncalendar(cron_schedule):
    """Convert a cron expression to a systemd OnCalendar value.

    Supports the common cron syntax: *, numbers, lists, ranges, */N and N/M
    steps, weekday names and @hourly-style macros.

    Raises:
        ValueError: If the expression uses syntax that has no systemd equivalent
    """
    cron_schedule = cron_schedule.strip()
    if cron_schedule in CRON_MACROS:
        return CRON_MACROS[cron_schedule]

    fields = cron_schedule.split()
    if len(fields) != 5:
        raise ValueError(f"expected 5 cron fields, got {len(fields)} in '{cron_schedule}'")
    minute, hour, day, month, weekday = fields

    # cron fires when EITHER day-of-month or day-of-week matches if both are
    # restricted; systemd requires both, so the result would silently differ.
    if day != "*" and weekday != "*":
        raise ValueError("schedules restricting both day-of-month and day-of-week have no systemd equivalent")

    calendar = "*-{}-{} {}:{}:00".format(
        _convert_cron_field(month, "month", 1),
        _convert_cron_field(day, "day-of-month", 1),
        _convert_cron_field(hour, "hour", 0),
        _convert_cron_field(minute, "minute", 0),
    )
    weekday = _convert_cron_weekday(weekday)
    return f"{weekday} {calendar}" if weekday else calendar


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
Environment={shlex.quote(f"SIGNALBOX_HOME={task_dir}")}
ExecStart={signalbox_cmd} group run {group_name}
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

    Raises:
            ValueError: If the group's cron schedule cannot be expressed as OnCalendar
    """
    service_name = f"signalbox-{group_name}"
    cron_schedule = get_schedule_string(group)
    on_calendar = cron_to_oncalendar(cron_schedule)

    return f"""[Unit]
Description=Timer for signalbox - {group.get('description', group_name)}
Requires={service_name}.service

[Timer]
# Converted from cron schedule: {cron_schedule}
# Verify with: systemd-analyze calendar '{on_calendar}'
OnCalendar={on_calendar}

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

    # Generate both files before writing anything so a bad schedule leaves no partial export
    try:
        timer_content = generate_systemd_timer(group, group_name)
    except ValueError as e:
        return ExportResult(success=False, error=f"Group '{group_name}' schedule can't be converted for systemd: {e}")
    service_content = generate_systemd_service(group, group_name)

    # Create export directory
    export_base_dir = resolve_path(get_config_value("paths.systemd_export_dir", "systemd"))
    export_dir = os.path.join(export_base_dir, group_name)
    os.makedirs(export_dir, exist_ok=True)

    service_name = f"signalbox-{group_name}"
    service_file = os.path.join(export_dir, f"{service_name}.service")
    timer_file = os.path.join(export_dir, f"{service_name}.timer")

    with open(service_file, "w") as f:
        f.write(service_content)

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

    home = shlex.quote(task_dir)
    return f"{get_schedule_string(group)} cd {home} && SIGNALBOX_HOME={home} {signalbox_cmd} group run {group_name}"


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
    export_base_dir = resolve_path(get_config_value("paths.cron_export_dir", "cron"))
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
