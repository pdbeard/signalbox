# Log commands: signalbox log show / history / list / tail / clear
import os
import sys
import time
from collections import deque
from datetime import datetime

import click

from ..config import load_config, get_config_value
from .. import log_manager
from ..executor import find_task
from ..helpers import get_resolved_log_dir
from .utils import handle_exceptions


@click.group()
def log():
    """See the log of each run, and delete old logs.

    \b
    Examples:
      signalbox log show backup        output of the latest run
      signalbox log list --failed      the latest failed runs of all tasks
      signalbox log history backup     every run of one task
      signalbox log tail backup        follow new runs as they happen
    """
    pass


@log.command(name="show")
@click.argument("name")
@handle_exceptions
def log_show(name):
    """Show the latest log for a task."""
    config = load_config()
    find_task(name, config)

    log_path, exists = log_manager.get_latest_log(name)
    if not exists:
        click.echo("No logs found")
        return

    # Use display settings from global config
    include_paths = get_config_value("display.include_paths", False)
    show_colors = get_config_value("display.colors", True)

    if include_paths:
        click.echo(f"Log file: {log_path}")
        click.echo("=" * 50)

    content = log_manager.read_log_content(log_path)
    formatted_lines = log_manager.format_log_with_colors(content, show_colors)

    for line, color in formatted_lines:
        if color:
            click.echo(click.style(line, fg=color))
        else:
            click.echo(line)


@log.command(name="history")
@click.argument("name")
@handle_exceptions
@click.pass_context
def log_history_cmd(ctx, name):
    """Show every run of a task: time, status and output preview (newest first)."""
    find_task(name, load_config())
    ctx.invoke(log_list_cmd, task=name, limit=None)


@log.command(name="list")
@click.option("--task", help="Show only this task")
@click.option("--status", type=click.Choice(["success", "failed"]), help="Filter by status")
@click.option("--failed", is_flag=True, help="Shortcut for --status failed")
@click.option("--success", is_flag=True, help="Shortcut for --status success")
@click.option("--since", help="Show logs since date (YYYY-MM-DD)")
@click.option("--until", help="Show logs until date (YYYY-MM-DD)")
@click.option("--today", is_flag=True, help="Show only today's logs")
@click.option("--last", "limit", type=click.IntRange(min=1), default=50, help="Show last N runs (default: 50)")
@click.option("--verbose", "-v", is_flag=True, help="Show the first lines of output of each log")
@handle_exceptions
def log_list_cmd(task, status, failed, success, since, until, today, limit, verbose):
    """Show the logs of all tasks. Use the options to filter them."""
    logs = log_manager.get_all_log_files()

    if not logs:
        click.echo("No logs found")
        return

    if failed:
        status = "failed"
    elif success:
        status = "success"

    since_dt = None
    until_dt = None

    if today and since:
        click.echo("Error: Use --today or --since, not both", err=True)
        sys.exit(2)
    if today:
        since_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif since:
        try:
            since_dt = datetime.strptime(since, "%Y-%m-%d")
        except ValueError:
            click.echo(f"Error: Invalid date format for --since: {since}. Use YYYY-MM-DD", err=True)
            sys.exit(2)

    if until:
        try:
            until_dt = datetime.strptime(until, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        except ValueError:
            click.echo(f"Error: Invalid date format for --until: {until}. Use YYYY-MM-DD", err=True)
            sys.exit(2)

    filtered_logs = log_manager.filter_logs(
        logs,
        task=task,
        status=status,
        since=since_dt,
        until=until_dt,
        limit=limit,
    )

    if not filtered_logs:
        click.echo("No logs found matching filters")
        return

    date_format = get_config_value("display.date_format", "%Y-%m-%d %H:%M:%S")

    if verbose:
        from ..cli_output import print_log_list_verbose

        log_rows = []
        for log_entry in filtered_logs:
            try:
                content = log_manager.read_log_content(log_entry["path"])
                log_rows.append(
                    {
                        "task": log_entry["task"],
                        "status": log_entry["metadata"]["status"],
                        "timestamp": log_entry["timestamp"].strftime(date_format),
                        "stdout": log_manager.parse_stdout_from_log(content),
                        "stderr": log_manager.parse_stderr_from_log(content),
                    }
                )
            except Exception as e:
                click.echo(f"[LOG ERROR] {e}", err=True)
        print_log_list_verbose(log_rows)
    else:
        from ..cli_output import print_log_list_table

        log_rows = []
        for log_entry in filtered_logs:
            try:
                log_rows.append(
                    {
                        "task": log_entry["task"],
                        "status": log_entry["metadata"]["status"],
                        "timestamp": log_entry["timestamp"].strftime(date_format),
                        "preview": log_entry["metadata"].get("preview", ""),
                    }
                )
            except Exception as e:
                click.echo(f"[LOG ERROR] {e}", err=True)
        print_log_list_table(log_rows)

    click.echo(f"Total: {len(filtered_logs)} log(s)")


@log.command(name="tail", short_help="Follow the log of a task, also its new runs.")
@click.argument("name")
@click.option("-f/-F", "--follow/--no-follow", default=True, help="Keep following new runs (default: follow)")
@click.option(
    "-n", "--lines", type=click.IntRange(min=0), default=10, help="Number of lines to show first (default: 10)"
)
@handle_exceptions
def log_tail_cmd(name, follow, lines):
    """Show the latest log for a task and follow new runs (like tail -f).

    Each run writes a new log file, so when a newer log appears the output
    switches to it instead of watching the old file forever.
    """
    config = load_config()
    find_task(name, config)

    log_path, exists = log_manager.get_latest_log(name)
    if not exists:
        click.echo(f"No logs found for task '{name}'")
        if not follow:
            return
        click.echo("Waiting for new logs... (Ctrl+C to stop)")

    try:
        while not exists:
            time.sleep(0.5)
            log_path, exists = log_manager.get_latest_log(name)

        click.echo(f"Following log: {log_path}")
        click.echo("─" * 50)

        f = open(log_path, "r", encoding="utf-8", errors="replace")
        try:
            for line in deque(f, maxlen=lines):
                click.echo(line, nl=False)

            while follow:
                line = f.readline()
                if line:
                    click.echo(line, nl=False)
                    continue
                newest, _ = log_manager.get_latest_log(name)
                if newest and newest != log_path:
                    f.close()
                    log_path = newest
                    f = open(log_path, "r", encoding="utf-8", errors="replace")
                    click.echo(f"\n── New run: {os.path.basename(log_path)} ──")
                    continue
                time.sleep(0.5)
        finally:
            f.close()
    except KeyboardInterrupt:
        click.echo("\nStopped following log")


@log.command(name="clear", short_help="Delete the logs of one task (--task) or all (--all).")
@click.option("--task", "task_name", help="Clear logs for specific task")
@click.option("--all", "clear_all", is_flag=True, help="Clear all logs for all tasks")
@click.option("--yes", "-y", is_flag=True, help="Do not ask for confirmation")
@handle_exceptions
def log_clear(task_name, clear_all, yes):
    """Clear logs and alert history for a specific task or all tasks."""
    if clear_all:
        log_dir = get_resolved_log_dir()
        if not yes and not click.confirm(f"Delete all task logs and alert history under {log_dir}?"):
            return
        if log_manager.clear_all_logs():
            click.echo("Cleared all logs")
        else:
            click.echo("No logs directory found")
    elif task_name:
        config = load_config()
        find_task(task_name, config)
        if log_manager.clear_task_logs(task_name):
            click.echo(f"Cleared logs for {task_name}")
        else:
            click.echo(f"No logs found for {task_name}")
    else:
        click.echo("Error: Give --task NAME or --all", err=True)
        sys.exit(2)
