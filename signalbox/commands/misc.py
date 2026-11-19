# Root-level commands: init, list-schedules, export-systemd, export-cron, notify-test, alerts
import os
import shutil
import sys
from datetime import datetime

import click

from ..config import load_config, find_init_home, find_entry
from .. import exporters
from .. import notifications
from .. import alerts
from ..helpers import format_timestamp, display_time
from .utils import handle_exceptions


@click.command()
def init():
    """Make the signalbox configuration directory (in SIGNALBOX_HOME or XDG_CONFIG_HOME, if set)."""
    # Never the current directory: reinitializing replaces what is there.
    config_dir = find_init_home()

    if os.path.exists(config_dir):
        click.echo(f"Configuration directory already exists: {config_dir}")
        backup_dir = f"{config_dir}.backup.{format_timestamp(datetime.now())}"
        if not click.confirm(
            f"Reinitialize? config/ and runtime/ are copied to {backup_dir}, then reset (logs are kept)"
        ):
            return
        # Only the directories being replaced are backed up; logs stay where they are.
        # Copy first and delete only after every copy succeeded, so nothing can be lost.
        replaced = [d for d in ("config", "runtime") if os.path.isdir(os.path.join(config_dir, d))]
        for subdir in replaced:
            shutil.copytree(os.path.join(config_dir, subdir), os.path.join(backup_dir, subdir), symlinks=True)
        if replaced:
            os.chmod(backup_dir, 0o700)  # the backup holds the same task commands
        click.echo(f"Backed up existing config to: {backup_dir}")
        for subdir in replaced:
            shutil.rmtree(os.path.join(config_dir, subdir))

    # The template config directory ships inside the signalbox package
    # (signalbox/config), one level above this commands/ subpackage.
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_config = os.path.join(package_dir, "config")

    if os.path.exists(template_config):
        # Copy the entire config directory
        shutil.copytree(template_config, os.path.join(config_dir, "config"))
        click.echo(f"✓ Created configuration directory: {config_dir}")
        click.echo(f"✓ Copied default config from: {template_config}")
    else:
        # Config directory not found - this should not happen in a proper installation
        click.echo(f"ERROR: Signalbox cannot find the configuration templates at: {template_config}", err=True)
        click.echo("Possibly, the package installation is not complete.", err=True)
        click.echo("Install signalbox again, or report the problem at:", err=True)
        click.echo("  https://github.com/pdbeard/signalbox/issues", err=True)
        sys.exit(1)

    # Create logs and runtime directories
    os.makedirs(os.path.join(config_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(config_dir, "runtime/tasks"), exist_ok=True)
    os.makedirs(os.path.join(config_dir, "runtime/groups"), exist_ok=True)
    # Task commands often hold tokens: keep the home private (what check-permissions expects)
    os.chmod(config_dir, 0o700)
    os.chmod(os.path.join(config_dir, "logs"), 0o700)

    click.echo(f"✓ Created logs directory: {config_dir}/logs")
    click.echo(f"✓ Created runtime directory: {config_dir}/runtime")
    click.echo()
    click.echo("Signalbox initialized successfully!")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Review configuration: {config_dir}/config/signalbox.yaml")
    click.echo(f"  2. Add your tasks: {config_dir}/config/tasks/")
    click.echo("     (example tasks are in config/catalog/; set include_catalog: true to load them)")
    click.echo("  3. Run: signalbox list")
    click.echo("SECURITY: Signalbox runs commands in a shell, with all your permissions.")
    click.echo("   Use only YAML files that you trust. Refer to:")
    click.echo("   https://github.com/pdbeard/signalbox/blob/main/documentation/SECURITY.md")
    click.echo("   You can now use signalbox in all directories.")


@click.command()
def list_schedules():
    """List all scheduled groups with their cron schedules."""
    config = load_config()
    groups = config.get("groups", [])
    scheduled = [g for g in groups if isinstance(g, dict) and "schedule" in g]

    if not scheduled:
        click.echo("No scheduled groups defined.")
        return

    from ..cli_output import print_schedule_list_table

    schedule_rows = []
    for group in scheduled:
        # Ensure all values are strings for rich table rendering
        group_name = str(group.get("name", ""))
        schedule = str(exporters.get_schedule_string(group))
        description = str(group.get("description", "N/A"))
        tasks_list = group.get("tasks", [])
        if isinstance(tasks_list, (list, tuple)):
            tasks_str = ", ".join([str(t) for t in tasks_list])
        else:
            tasks_str = str(tasks_list)
        task_count = str(len(tasks_list)) if isinstance(tasks_list, (list, tuple)) else "1"
        schedule_rows.append(
            {
                "group": group_name,
                "schedule": schedule,
                "description": description,
                "task_count": task_count,
                "tasks": tasks_str,
            }
        )
    print_schedule_list_table(schedule_rows)


@click.command()
@click.argument("group_name")
@click.option("--user", is_flag=True, help="Make a user unit (not a system unit)")
def export_systemd(group_name, user):
    """Generate systemd service and timer files for a scheduled group."""
    group = find_entry(load_config(), "groups", group_name)

    result = exporters.export_systemd(group, group_name, user=user)

    if not result.success:
        click.echo(f"Error: {result.error}", err=True)
        sys.exit(1)

    # Show generated files
    for file_path in result.files:
        click.echo(f"✓ Generated {file_path}")

    # Show installation instructions
    click.echo("")
    instructions = exporters.get_systemd_install_instructions(result.files[0], result.files[1], group_name, user)
    for instruction in instructions:
        click.echo(instruction)


@click.command()
@click.argument("group_name")
@click.option(
    "--install", is_flag=True, help="Also add the entry to your crontab (replaces an older one for this group)"
)
@handle_exceptions
def export_cron(group_name, install):
    """Generate crontab entry for a scheduled group."""
    group = find_entry(load_config(), "groups", group_name)

    result = exporters.export_cron(group, group_name)

    if not result.success:
        click.echo(f"Error: {result.error}", err=True)
        sys.exit(1)

    # Show generated file
    click.echo(f"✓ Generated {result.files[0]}")
    if install:
        replaced = exporters.install_cron_entry(result.cron_entry, group_name)
        click.echo(f"✓ {'Updated' if replaced else 'Added'} the entry in your crontab:")
        click.echo(result.cron_entry)
        return
    click.echo("")

    # Show installation instructions
    instructions = exporters.get_cron_install_instructions(result.files[0], result.cron_entry, group)
    for instruction in instructions:
        click.echo(instruction)


@click.command()
@click.option("--title", default="Signalbox Test", help="Notification title")
@click.option("--message", default="This is a test notification from Signalbox", help="Notification message")
@click.option(
    "--urgency",
    type=click.Choice(["low", "normal", "critical"]),
    default="normal",
    help="Notification urgency level (Linux only)",
)
@handle_exceptions
def notify_test(title, message, urgency):
    """Send a test notification to make sure that notifications work."""
    import platform

    system = platform.system()
    click.echo(f"Sending test notification on {system}...")
    click.echo(f"Title: {title}")
    click.echo(f"Message: {message}")
    if system == "Linux":
        click.echo(f"Urgency: {urgency}")

    success = notifications.send_notification(title, message, urgency)

    if success:
        click.echo("✓ Notification sent successfully!")
    else:
        click.echo("✗ Signalbox could not send the notification. Look for a warning above.", err=True)
        sys.exit(1)


@click.command()
@click.argument("task_name", required=False)
@click.option("--severity", type=click.Choice(["info", "warning", "critical"]), help="Filter by severity")
@click.option("--days", type=int, help="Show alerts from last N days")
@handle_exceptions
def alerts_cmd(task_name, severity, days):
    """Show the recent alerts. You can filter them by task name, severity or age."""

    # Load alerts with filters
    alert_list = alerts.load_alerts(task_name=task_name, severity=severity, max_days=days)

    if not alert_list:
        if task_name:
            click.echo(f"No alerts found for task '{task_name}'")
        else:
            click.echo("No alerts found")
        return

    for alert in alert_list:
        human_date = display_time(alert.get("timestamp", ""))

        severity_str = alert.get("severity", "info")
        task = alert.get("task_name", "unknown")
        message = alert.get("message", "")

        # Color code by severity
        if severity_str == "critical":
            severity_label = click.style(severity_str, fg="red", bold=True)
        elif severity_str == "warning":
            severity_label = click.style(severity_str, fg="yellow")
        else:
            severity_label = click.style(severity_str, fg="blue")

        click.echo(f"[{human_date}] [{severity_label}] {task}: {message}")

    # Show summary
    click.echo(f"\nTotal alerts: {len(alert_list)}")


# Monitoring-plugin convention (Nagios and similar): 0 OK, 1 warning, 2 critical
STATUS_EXIT_CODES = {"green": 0, "yellow": 1, "red": 2}
ROW_COLOURS = {"success": "green", "failed": "red", "partial": "red", "overdue": "yellow", "skipped": "bright_black"}


@click.command()
@handle_exceptions
def status():
    """Show what the tray shows: failures and overdue groups.

    Exits 0 when all is OK, 1 when a scheduled group is overdue and 2 when
    something failed, so cron, systemd or a monitoring tool can check it on a
    machine without a tray.
    """
    from ..tray_status import read_status

    result = read_status()
    click.echo(result["tooltip"])
    for title, kind in (("Groups", "groups"), ("Tasks", "tasks")):
        if result[kind]:
            click.echo(f"\n{title}:")
        for icon, name, detail, row_status in result[kind]:
            click.echo(f"  {click.style(icon, fg=ROW_COLOURS.get(row_status))} {name}  {detail}")
    sys.exit(STATUS_EXIT_CODES[result["colour"]])
