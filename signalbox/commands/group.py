# Group commands: signalbox group run / list
from datetime import datetime

import click

from ..config import load_config
from ..executor import run_group_parallel, run_group_serial
from ..runtime import save_group_runtime_state, load_runtime_state
from ..exceptions import GroupNotFoundError
from ..helpers import format_timestamp
from .utils import handle_exceptions
from .task import _latest_log_name


@click.group()
def group():
    """
    Manage and run task groups.

    \b
    Commands:
      run NAME    Run a group of tasks
      list        List all configured groups
    """
    pass


@group.command(name="run")
@click.argument("name")
@handle_exceptions
def group_run(name):
    """Run a group of tasks."""
    config = load_config()
    groups = config.get("groups", [])
    group_item = next((g for g in groups if g["name"] == name), None)
    if not group_item:
        raise GroupNotFoundError(name)
    execution_mode = group_item.get("execution", "serial")
    stop_on_error = group_item.get("stop_on_error", False)
    click.echo(f"Running group {name}: {group_item['description']}")
    if execution_mode == "parallel":
        click.echo("Execution mode: parallel")
    else:
        click.echo(f"Execution mode: serial (stop_on_error: {stop_on_error})")
    task_names = group_item["tasks"]
    start_time = datetime.now()
    timestamp = format_timestamp(start_time)
    from ..cli_output_run import print_group_run_table

    # Run all tasks in a single call so parallel/serial semantics are correct.
    if execution_mode == "parallel":
        run_group_parallel(task_names, config)
    else:
        run_group_serial(task_names, config, stop_on_error)

    # Collect per-task results for the status table from runtime state + log files.
    runtime = load_runtime_state()
    results = []
    for task_name in task_names:
        task_state = runtime.get("tasks", {}).get(task_name, {})
        status = task_state.get("last_status", "unknown")
        results.append(
            {
                "name": task_name,
                "status": status,
                "log_file": _latest_log_name(task_name),
                "error": "",
            }
        )
    end_time = datetime.now()
    execution_time = (end_time - start_time).total_seconds()
    tasks_total = len(task_names)
    tasks_successful = sum(1 for r in results if r["status"] == "success")
    if tasks_successful == tasks_total:
        group_status = "success"
    elif tasks_successful > 0:
        group_status = "partial"
    else:
        group_status = "failed"

    # Save group runtime state
    group_source_file = config["_group_sources"].get(name)
    if group_source_file:
        save_group_runtime_state(
            group_name=name,
            source_file=group_source_file,
            last_run=timestamp,
            last_status=group_status,
            execution_time=execution_time,
            tasks_total=tasks_total,
            tasks_successful=tasks_successful,
        )

    print_group_run_table(results)
    click.echo(f"Group {name} executed.")


@group.command(name="list")
def group_list():
    """List all available groups and their tasks."""
    config = load_config()
    groups = config.get("groups", [])
    if not groups:
        click.echo("No groups defined.")
        return
    from ..cli_output_group import print_group_list_table

    group_rows = []
    for group_item in groups:
        try:
            group_rows.append(
                {
                    "name": group_item.get("name", ""),
                    "description": group_item.get("description", ""),
                    "schedule": group_item.get("schedule", ""),
                    "execution": group_item.get("execution", "serial"),
                    "stop_on_error": group_item.get("stop_on_error", False),
                    "tasks": group_item.get("tasks", []),
                }
            )
        except KeyError as e:
            click.echo(
                f"[CONFIG ERROR] Group entry missing required field: {e}. Offending group: {group_item}", err=True
            )
        except Exception as e:
            click.echo(f"[CONFIG ERROR] Unexpected error in group config: {e}. Offending group: {group_item}", err=True)
    print_group_list_table(group_rows)
