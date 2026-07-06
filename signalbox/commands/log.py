# Log commands: signalbox log show / history / list / tail / clear
import os
import subprocess
import sys
import time
from datetime import datetime

import click

from ..config import load_config, get_config_value
from .. import log_manager
from ..exceptions import TaskNotFoundError
from .utils import handle_exceptions


def _find_task_or_raise(config, name):
    """Return the task dict for name or raise TaskNotFoundError."""
    task = next((t for t in config["tasks"] if t["name"] == name), None)
    if not task:
        raise TaskNotFoundError(name)
    return task


@click.group()
def log():
    """
    View and manage execution logs.

    \b
    Commands:
      list [OPTIONS]     List all task execution logs with filters
      show TASK          Show the latest log for a task
      tail TASK          Follow log output in real-time
      history TASK       Show all historical logs for a task
      clear [OPTIONS]    Clear logs for tasks
    """
    pass


@log.command(name="show")
@click.argument("name")
@handle_exceptions
def log_show(name):
    """Show the latest log for a task."""
    config = load_config()
    _find_task_or_raise(config, name)

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
def log_history_cmd(name):
    """Show all historical log files for a task."""
    config = load_config()
    _find_task_or_raise(config, name)

    log_info, exists = log_manager.get_log_history(name)
    if not exists:
        click.echo("No history found")
        return

    # Use display settings from global config
    include_paths = get_config_value("display.include_paths", False)
    date_format = get_config_value("display.date_format", "%Y-%m-%d %H:%M:%S")

    task_log_dir = log_manager.get_task_log_dir(name)
    path_info = f" ({task_log_dir})" if include_paths else ""
    click.echo(f"Log history for {name}{path_info}:")

    for filename, mtime in log_info:
        time_str = datetime.fromtimestamp(mtime).strftime(date_format)
        click.echo(f"  {filename} - {time_str}")


@log.command(name="list")
@click.option("--task", help="Filter to specific task")
@click.option("--status", type=click.Choice(["success", "failed"]), help="Filter by status")
@click.option("--failed", is_flag=True, help="Shortcut for --status failed")
@click.option("--success", is_flag=True, help="Shortcut for --status success")
@click.option("--since", help="Show logs since date (YYYY-MM-DD)")
@click.option("--until", help="Show logs until date (YYYY-MM-DD)")
@click.option("--today", is_flag=True, help="Show only today's logs")
@click.option("--last", "limit", type=int, default=50, help="Show last N runs (default: 50)")
@click.option("--verbose", "-v", is_flag=True, help="Show truncated output for each log entry")
@handle_exceptions
def log_list_cmd(task, status, failed, success, since, until, today, limit, verbose):
    """List all task execution logs with filters."""
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
        from ..cli_output_tables import print_log_list_verbose

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
        from ..cli_output_tables import print_log_list_table

        log_rows = []
        for log_entry in filtered_logs:
            try:
                log_rows.append(
                    {
                        "task": log_entry["task"],
                        "status": log_entry["metadata"]["status"],
                        "timestamp": log_entry["timestamp"].strftime(date_format),
                        "preview": log_entry["metadata"].get("stdout_preview", ""),
                    }
                )
            except Exception as e:
                click.echo(f"[LOG ERROR] {e}", err=True)
        print_log_list_table(log_rows)

    click.echo(f"Total: {len(filtered_logs)} log(s)")


@log.command(name="tail")
@click.argument("name")
@click.option("-f", "--follow", is_flag=True, default=True, help="Follow log output (default)")
@click.option("-n", "--lines", type=int, default=10, help="Number of lines to show initially (default: 10)")
@handle_exceptions
def log_tail_cmd(name, follow, lines):
    """Follow log output in real-time (like tail -f)."""
    config = load_config()
    _find_task_or_raise(config, name)

    log_path, exists = log_manager.get_latest_log(name)
    if not exists:
        click.echo(f"No logs found for task '{name}'")
        click.echo("Waiting for new logs... (Ctrl+C to stop)")

        # Wait for log file to appear
        while not exists:
            time.sleep(0.5)
            log_path, exists = log_manager.get_latest_log(name)

    click.echo(f"Following log: {log_path}")
    click.echo("─" * 50)

    # Use tail -f on Unix-like systems
    if os.name != "nt":  # Not Windows
        try:
            subprocess.run(["tail", f"-n{lines}", "-f", log_path])
        except KeyboardInterrupt:
            click.echo("\nStopped following log")
    else:
        # Simple Python implementation for cross-platform
        try:
            with open(log_path, "r") as f:
                # Show last N lines
                lines_buffer = []
                for line in f:
                    lines_buffer.append(line)
                    if len(lines_buffer) > lines:
                        lines_buffer.pop(0)

                for line in lines_buffer:
                    click.echo(line, nl=False)

                # Follow new content
                if follow:
                    while True:
                        line = f.readline()
                        if line:
                            click.echo(line, nl=False)
                        else:
                            time.sleep(0.1)
        except KeyboardInterrupt:
            click.echo("\nStopped following log")


@log.command(name="clear")
@click.option("--task", "task_name", help="Clear logs for specific task")
@click.option("--all", "clear_all", is_flag=True, help="Clear all logs for all tasks")
@handle_exceptions
def log_clear(task_name, clear_all):
    """Clear logs for a specific task or all tasks."""
    if clear_all:
        if log_manager.clear_all_logs():
            click.echo("Cleared all logs")
        else:
            click.echo("No logs directory found")
    elif task_name:
        config = load_config()
        _find_task_or_raise(config, task_name)
        if log_manager.clear_task_logs(task_name):
            click.echo(f"Cleared logs for {task_name}")
        else:
            click.echo(f"No logs found for {task_name}")
    else:
        click.echo("Error: Provide --task NAME or --all", err=True)
        sys.exit(2)
