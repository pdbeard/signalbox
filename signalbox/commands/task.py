# Task commands: signalbox task run / list
import os
import sys

import click

from ..config import load_config, get_config_value
from ..executor import run_task
from ..runtime import load_runtime_state, merge_config_with_runtime_state
from .. import log_manager
from ..exceptions import SignalboxError
from ..helpers import parse_timestamp
from .utils import handle_exceptions, print_run_output_preview


@click.group()
def task():
    """
    Manage and run tasks.

    \b
    Commands:
      run [NAME|--all]   Run a single task or all tasks
      list               List all configured tasks with status
    """
    pass


@task.command(name="list")
def task_list():
    """List all tasks and their status, grouped by config file."""
    config = load_config()
    runtime_state = load_runtime_state()
    config = merge_config_with_runtime_state(config, runtime_state)

    date_format = get_config_value("display.date_format", "%Y-%m-%d %H:%M:%S")
    # Group tasks by their source file
    task_sources = config.get("_task_sources", {})
    tasks_by_file = {}
    for task_item in config["tasks"]:
        source = task_sources.get(task_item.get("name"), "<unknown source>")
        tasks_by_file.setdefault(source, []).append(task_item)

    # Flatten all tasks with their source file for a single table
    from ..cli_output import print_task_list_table

    all_rows = []
    for source_file, tasks in tasks_by_file.items():
        file_name = os.path.basename(source_file)
        for task_item in tasks:
            try:
                name = task_item.get("name", "")
                status = task_item.get("last_status", "not run")
                last_run = task_item.get("last_run", "")
                description = task_item.get("description", "")
                # Format last run
                if last_run:
                    try:
                        timestamp_str = last_run.replace(".log", "")
                        dt = parse_timestamp(timestamp_str)
                        last_run_str = dt.strftime(date_format)
                    except Exception:
                        last_run_str = last_run
                else:
                    last_run_str = ""
                all_rows.append(
                    {
                        "name": name,
                        "status": status,
                        "last_run": last_run_str,
                        "description": description,
                        "source": file_name,
                    }
                )
            except KeyError as e:
                click.echo(
                    f"[CONFIG ERROR] Task entry missing required field: {e}. Offending task: {task_item}", err=True
                )
            except Exception as e:
                click.echo(
                    f"[CONFIG ERROR] Unexpected error in task config: {e}. Offending task: {task_item}", err=True
                )
    print_task_list_table(all_rows)


def _latest_log_name(task_name):
    """Return the filename of the newest log for a task, or '' if none exists."""
    try:
        log_path, exists = log_manager.get_latest_log(task_name)
        return os.path.basename(log_path) if exists else ""
    except Exception:
        return ""


@task.command(name="run")
@click.argument("name", required=False)
@click.option("--all", "run_all_tasks", is_flag=True, help="Run all tasks")
@click.option("--quiet", "-q", is_flag=True, help="Suppress inline output preview")
@handle_exceptions
def task_run(name, run_all_tasks, quiet):
    """Run a single task or all tasks."""
    if run_all_tasks:
        config = load_config(suppress_warnings=True)
        click.echo("Running all tasks...")
        from ..cli_output_run import print_task_run_table

        results = []
        for task_item in config["tasks"]:
            name = task_item["name"]
            error = ""
            try:
                click.echo(f"Running {name}...")
                success = run_task(name, config)
                status = "success" if success else "failed"
            except SignalboxError as e:
                status = "failed"
                error = str(e)
            except Exception as e:
                status = "failed"
                error = str(e)
            results.append(
                {
                    "name": name,
                    "status": status,
                    "log_file": _latest_log_name(name),
                    "error": error,
                }
            )
        print_task_run_table(results)
        failed_tasks = [r["name"] for r in results if r["status"] != "success"]
        if failed_tasks:
            click.echo(f"\n{len(failed_tasks)} task(s) failed: {', '.join(failed_tasks)}", err=True)
            sys.exit(1)
        else:
            click.echo("\nAll tasks completed successfully")
            sys.exit(0)
    elif name:
        config = load_config(suppress_warnings=True)
        success = run_task(name, config)
        if not quiet:
            log_path, exists = log_manager.get_latest_log(name)
            if exists:
                content = log_manager.read_log_content(log_path)
                stdout = log_manager.parse_stdout_from_log(content)
                stderr = log_manager.parse_stderr_from_log(content)
                print_run_output_preview(stdout, stderr if not success else "", name)
        if not success:
            sys.exit(1)
    else:
        click.echo("Error: Provide task name or use --all", err=True)
        sys.exit(2)
