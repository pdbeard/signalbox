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
from ..exceptions import ValidationError
from ..validator import validate_run_settings
from .utils import handle_exceptions, no_config_message


@click.command(short_help="Make the configuration (do this first).")
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
    click.echo("Signalbox initialized successfully! You can now use signalbox in all directories.")
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Try the example task:   signalbox run hello")
    click.echo("  2. See all tasks:          signalbox list")
    click.echo(f"  3. Add your own tasks in:  {config_dir}/config/tasks/")
    click.echo("     (more examples are in config/catalog/; set include_catalog: true to load them)")
    click.echo(
        "  4. Step-by-step tutorial:  https://github.com/pdbeard/signalbox/blob/main/documentation/QUICKSTART.md"
    )
    click.echo()
    click.echo("Security: signalbox runs commands in a shell, with all your permissions.")
    click.echo("Use only YAML files that you trust. Refer to:")
    click.echo("  https://github.com/pdbeard/signalbox/blob/main/documentation/SECURITY.md")


@click.command(short_help="Scheduled groups: when they run, and when next.")
def list_schedules():
    """List the scheduled groups: when they run, and when they run next."""
    from ..cli_output import print_schedule_list_table
    from ..cron import describe, next_due_time

    config = load_config()
    scheduled = [g for g in config.get("groups", []) if isinstance(g, dict) and "schedule" in g]
    if not scheduled:
        click.echo(no_config_message(config) or "No scheduled groups defined.")
        return

    now = datetime.now()
    schedule_rows = []
    for group in scheduled:
        schedule = str(exporters.get_schedule_string(group))
        upcoming = next_due_time(schedule, now)
        tasks = group.get("tasks", [])
        schedule_rows.append(
            {
                "group": str(group.get("name", "")),
                "when": describe(schedule),
                "schedule": schedule,
                "next": f"{upcoming:%a %d %b %H:%M}" if upcoming else "",
                "tasks": ", ".join(str(t) for t in tasks) if isinstance(tasks, list) else str(tasks),
            }
        )
    print_schedule_list_table(schedule_rows)


@click.command(short_help="Make systemd timer files for a scheduled group.")
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


@click.command(short_help="Make (and --install) crontab lines for scheduled groups.")
@click.argument("group_name", required=False)
@click.option("--all", "export_all", is_flag=True, help="Every group that has a schedule")
@click.option(
    "--install",
    is_flag=True,
    help="Also put the entries in your crontab (replaces older ones; makes a backup first)",
)
@handle_exceptions
def export_cron(group_name, export_all, install):
    """Generate crontab entries for one scheduled group, or for all of them (--all).

    With --install, signalbox also changes your crontab: it replaces the earlier
    lines of these groups, adds or removes the catch-up line (scheduling.catch_up_minutes),
    and keeps all other lines. It saves the old crontab in backups/ first.
    """
    if bool(group_name) == export_all:
        click.echo("Error: Give a group name or --all", err=True)
        sys.exit(2)
    config = load_config()
    if export_all:
        names = [g["name"] for g in config.get("groups", []) if isinstance(g, dict) and "schedule" in g]
        if not names:
            click.echo("No scheduled groups defined.")
    else:
        names = [group_name]

    results = []
    for name in names:
        result = exporters.export_cron(find_entry(config, "groups", name), name)
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            sys.exit(1)
        click.echo(f"✓ Generated {result.files[0]}")
        results.append(result)

    if install:
        # The catch-up line goes in with the entries: an invalid setting must not reach the crontab
        errors = validate_run_settings()
        if errors:
            raise ValidationError("; ".join(errors))
        entries = [r.cron_entry for r in results]
        removed, backup = exporters.install_cron_entries(entries, None if export_all else names)
        if backup is None:
            click.echo("Your crontab already has these entries. Nothing changed.")
        else:
            click.echo(f"✓ Updated your crontab ({removed} old line(s) replaced). Old crontab saved to: {backup}")
        for entry in entries:
            click.echo(entry)
        minutes = exporters.catch_up_minutes()
        click.echo(
            f"Catch-up: {'every %d minutes (run-overdue)' % minutes if minutes else 'off'} (scheduling.catch_up_minutes)"
        )
        return

    if len(results) == 1:
        click.echo("")
        group = find_entry(config, "groups", names[0])
        for instruction in exporters.get_cron_install_instructions(results[0].files[0], results[0].cron_entry, group):
            click.echo(instruction)
    else:
        for result in results:
            click.echo(result.cron_entry)


@click.command(short_help="Send a test desktop notification.")
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


@click.command(short_help="Show the recent alerts.")
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
ROW_COLOURS = {
    "success": "green",
    "failed": "red",
    "partial": "red",
    "alert": "red",
    "overdue": "yellow",
    "skipped": "bright_black",
}


@click.command(short_help="Show whether everything ran and passed.")
@handle_exceptions
def status():
    """Show whether everything ran and passed: each group and task, failures,
    groups that did not run when due, and alerts from the latest runs.

    \b
    Exit codes (for scripts and monitoring tools such as Nagios):
      0  all OK
      1  a scheduled group is overdue, a task raised a warning alert,
         or a task skipped too many runs
      2  something failed, or raised a critical alert
      3  no configuration (run: signalbox init)
    """
    from ..tray_status import read_status

    missing = no_config_message(load_config(suppress_warnings=True))
    if missing:
        click.echo(missing)
        sys.exit(3)
    result = read_status()
    click.echo(f"signalbox: {result['summary']}")
    if result["attention"]:
        click.echo("\nNeeds attention:")
        for colour, name, reason in result["attention"]:
            click.echo(f"  {click.style('■', fg=colour)} {name}  {reason}")
        click.echo("  Details: signalbox log show TASK, signalbox alerts")

    def row(icon, name, detail, row_status, indent="  "):
        click.echo(f"{indent}{click.style(icon, fg=ROW_COLOURS.get(row_status))} {name}  {detail}")

    if result["groups"]:
        click.echo("\nGroups:")
    for group_row in result["groups"]:
        row(*group_row)
        for task_row in result["group_tasks"].get(group_row[1], []):
            row(*task_row, indent="      ")
    if result["other_tasks"]:
        click.echo("\nOther tasks:" if result["groups"] else "\nTasks:")
    for task_row in result["other_tasks"]:
        row(*task_row)
    sys.exit(STATUS_EXIT_CODES[result["colour"]])


@click.command(name="run-overdue", short_help="Run the scheduled groups that missed their time.")
@handle_exceptions
def run_overdue():
    """Run each scheduled group that did not run when it was due.

    For example, cron does not run a job while the computer is asleep. Set
    scheduling.catch_up_minutes and run `signalbox export-cron --all --install`
    to let cron run this command regularly. A group counts as overdue by the same
    rule as in the tray and `signalbox status`, so a group that cron just ran is
    not run again.
    """
    import fcntl

    from ..config import resolve_path
    from ..tray_status import read_status
    from .group import run_group
    from ..exceptions import SignalboxError

    # One catch-up at a time: a group is recorded only when it ends, so a second catch-up
    # that starts while a slow group still runs would see it as overdue and start it again
    os.makedirs(resolve_path("runtime"), exist_ok=True)
    lock = open(resolve_path("runtime/.run-overdue.lock"), "w")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        click.echo("A catch-up is already running.")
        return

    overdue = [name for _icon, name, _detail, status in read_status()["groups"] if status == "overdue"]
    if not overdue:
        click.echo("No group is overdue.")
        return
    failed = []
    for name in overdue:
        click.echo(f"\nCatching up: {name}")
        try:
            status = run_group(name)
        except SignalboxError as e:
            click.echo(f"Error: {e.message}", err=True)
            status = "failed"
        if status not in ("success", "skipped"):
            failed.append(name)
    if failed:
        click.echo(f"\n{len(failed)} group(s) failed: {', '.join(failed)}", err=True)
        sys.exit(1)
