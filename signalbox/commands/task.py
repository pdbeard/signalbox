# Task commands: signalbox task run / list
import os
import sys

import click

from ..config import load_config
from ..executor import run_task, find_task, last_log_name
from ..runtime import load_runtime_state, merge_config_with_runtime_state
from .. import log_manager
from ..exceptions import ValidationError, TaskSkipped
from ..helpers import display_time
from ..validator import validate_task_for_run
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
@handle_exceptions
def task_list():
    """List all tasks and their status, grouped by config file."""
    config = load_config()
    runtime_state = load_runtime_state()
    config = merge_config_with_runtime_state(config, runtime_state)

    # Group tasks by their source file
    task_sources = config.get("_task_sources", {})
    tasks_by_file = {}
    for task_item in config["tasks"]:
        # A non-mapping entry is kept so the loop below reports it as a config error
        name = task_item.get("name") if isinstance(task_item, dict) else None
        source = task_sources.get(name, "<unknown source>")
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
                description = task_item.get("description", "")
                all_rows.append(
                    {
                        "name": name,
                        "status": status,
                        "last_run": display_time(task_item.get("last_run", "")),
                        "description": description,
                        "source": file_name,
                    }
                )
            except Exception as e:
                click.echo(
                    f"[CONFIG ERROR] Unexpected error in the task configuration: {e}. Task: {task_item}", err=True
                )
    print_task_list_table(all_rows)


@task.command(name="run")
@click.argument("name", required=False)
@click.option("--all", "run_all_tasks", is_flag=True, help="Run all tasks")
@click.option("--quiet", "-q", is_flag=True, help="Do not show the output preview")
@handle_exceptions
def task_run(name, run_all_tasks, quiet):
    """Run a single task or all tasks."""
    if run_all_tasks:
        config = load_config(suppress_warnings=True)
        click.echo("Running all tasks...")
        from ..cli_output import print_run_table

        results = []
        for task_item in config["tasks"]:
            # run_task reports a nameless or malformed entry as a validation error
            name = task_item.get("name") if isinstance(task_item, dict) else None
            error = ""
            try:
                click.echo(f"Running {name or '<unnamed>'}...")
                if not isinstance(task_item, dict):
                    # run_task looks tasks up by name, which a non-mapping entry has not got
                    raise ValidationError("; ".join(validate_task_for_run(task_item)))
                success = run_task(name, config)
                status = "success" if success else "failed"
            except TaskSkipped as e:
                status = "skipped"
                error = e.reason
            except Exception as e:
                status = "failed"
                error = str(e)
            results.append(
                {
                    "name": name or "<unnamed>",
                    "status": status,
                    "log_file": last_log_name(name, config),
                    "error": error,
                }
            )
        # A file that failed to load has tasks that never ran: that is a failure, not "all OK"
        results += [
            {"name": os.path.basename(path), "status": "failed", "log_file": "", "error": f"{path}: {message}"}
            for path, message in config.get("_load_errors", {}).items()
        ]
        print_run_table(results)
        failed_tasks = [r["name"] for r in results if r["status"] == "failed"]  # a skip is not a failure
        if failed_tasks:
            click.echo(f"\n{len(failed_tasks)} task(s) failed: {', '.join(failed_tasks)}", err=True)
            sys.exit(1)
        else:
            click.echo("\nAll tasks completed successfully")
            sys.exit(0)
    elif name:
        # Warnings on: a task in a file that does not load would otherwise just be "not found"
        config = load_config()
        try:
            success = run_task(name, config)
        except TaskSkipped:
            return  # run_task has said why; a skip is not a failure (exit 0)
        # The log this run wrote, not the newest file: a scheduled run of the same task may have finished since
        log_path = find_task(name, config).get("last_log")
        if not quiet and log_path:
            content = log_manager.read_log_content(log_path)
            stdout = log_manager.parse_stdout_from_log(content)
            stderr = log_manager.parse_stderr_from_log(content)
            print_run_output_preview(stdout, stderr if not success else "", name)
        if not success:
            sys.exit(1)
    else:
        click.echo("Error: Give a task name, or use --all", err=True)
        sys.exit(2)
