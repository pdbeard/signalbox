# Root-level commands: init, list-schedules, export-systemd, export-cron, notify-test, alerts
import os
import shutil
import sys
from datetime import datetime

import click

from ..config import load_config, get_config_value, find_config_home
from .. import exporters
from .. import notifications
from .. import alerts
from ..helpers import format_timestamp, parse_timestamp
from .utils import handle_exceptions


@click.command()
def init():
    """Initialize signalbox configuration in the appropriate config directory (XDG/SIGNALBOX_HOME supported)"""
    config_dir = find_config_home()

    if os.path.exists(config_dir):
        click.echo(f"Configuration directory already exists: {config_dir}")
        if not click.confirm("Do you want to reinitialize (this will backup existing config)?"):
            return
        # Backup existing config
        backup_dir = f"{config_dir}.backup.{format_timestamp(datetime.now())}"
        shutil.move(config_dir, backup_dir)
        click.echo(f"Backed up existing config to: {backup_dir}")

    # Find the installed package's config templates.
    # The template config directory ships inside the signalbox package
    # (signalbox/config), one level above this commands/ subpackage.
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_config = os.path.join(package_dir, "config")

    # If not found there, try using pkg_resources (older installations)
    if not os.path.exists(template_config):
        try:
            import pkg_resources

            package_path = pkg_resources.resource_filename("signalbox", "config")
            if os.path.exists(package_path):
                template_config = package_path
        except Exception:
            pass

    if os.path.exists(template_config):
        # Copy the entire config directory
        shutil.copytree(template_config, os.path.join(config_dir, "config"))
        click.echo(f"✓ Created configuration directory: {config_dir}")
        click.echo(f"✓ Copied default config from: {template_config}")
    else:
        # Config directory not found - this should not happen in a proper installation
        click.echo(f"ERROR: Could not find config templates at: {template_config}", err=True)
        click.echo("This may indicate an incomplete package installation.", err=True)
        click.echo("Please reinstall signalbox or file an issue at:", err=True)
        click.echo("  https://github.com/pdbeard/signalbox/issues", err=True)
        sys.exit(1)

    # Create logs and runtime directories
    os.makedirs(os.path.join(config_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(config_dir, "runtime/tasks"), exist_ok=True)
    os.makedirs(os.path.join(config_dir, "runtime/groups"), exist_ok=True)

    click.echo(f"✓ Created logs directory: {config_dir}/logs")
    click.echo(f"✓ Created runtime directory: {config_dir}/runtime")
    click.echo()
    click.echo("Signalbox initialized successfully!")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Review configuration: {config_dir}/config/signalbox.yaml")
    click.echo(f"  2. Add your tasks: {config_dir}/config/tasks/")
    click.echo("  3. Run: signalbox list")
    click.echo("SECURITY: Signalbox executes commands with full shell access.")
    click.echo("   Only use trusted YAML files. See SECURITY.md for details.")
    click.echo("   You can now run signalbox from any directory!")


@click.command()
def list_schedules():
    """List all scheduled groups with their cron schedules."""
    config = load_config()
    groups = config.get("groups", [])
    scheduled = [g for g in groups if "schedule" in g]

    if not scheduled:
        click.echo("No scheduled groups defined.")
        return

    from ..cli_output_tables import print_schedule_list_table

    schedule_rows = []
    for group in scheduled:
        # Ensure all values are strings for rich table rendering
        group_name = str(group.get("name", ""))
        schedule = str(group.get("schedule", ""))
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
@click.option("--user", is_flag=True, help="Generate for user systemd (not system-wide)")
def export_systemd(group_name, user):
    """Generate systemd service and timer files for a scheduled group."""
    config = load_config()
    groups = config.get("groups", [])
    group = next((g for g in groups if g["name"] == group_name), None)

    result = exporters.export_systemd(group, group_name)

    if not result.success:
        click.echo(f"Error: {result.error}")
        return

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
def export_cron(group_name):
    """Generate crontab entry for a scheduled group."""
    config = load_config()
    groups = config.get("groups", [])
    group = next((g for g in groups if g["name"] == group_name), None)

    result = exporters.export_cron(group, group_name)

    if not result.success:
        click.echo(f"Error: {result.error}")
        return

    # Show generated file
    click.echo(f"✓ Generated {result.files[0]}")
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
    """Send a test notification to verify notification system works."""
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
        click.echo("✗ Failed to send notification. Check logs for details.", err=True)
        sys.exit(1)


@click.command()
@click.argument("task_name", required=False)
@click.option("--severity", type=click.Choice(["info", "warning", "critical"]), help="Filter by severity")
@click.option("--days", type=int, help="Show alerts from last N days")
@handle_exceptions
def alerts_cmd(task_name, severity, days):
    """List recent alerts. Optionally filter by task name, severity, or time range."""

    # Load alerts with filters
    alert_list = alerts.load_alerts(task_name=task_name, severity=severity, max_days=days)

    if not alert_list:
        if task_name:
            click.echo(f"No alerts found for task '{task_name}'")
        else:
            click.echo("No alerts found")
        return

    # Display alerts
    date_format = get_config_value("display.date_format", "%Y-%m-%d %H:%M:%S")

    for alert in alert_list:
        timestamp_str = alert.get("timestamp", "")
        try:
            dt = parse_timestamp(timestamp_str)
            human_date = dt.strftime(date_format)
        except Exception:
            human_date = timestamp_str

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
