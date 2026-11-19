# Group commands: signalbox group run / list
import sys
from datetime import datetime

import click

from ..config import load_config, find_entry
from ..executor import run_group_parallel, run_group_serial
from ..cron import describe
from ..exporters import get_schedule_string
from ..runtime import save_group_runtime_state
from ..exceptions import GroupNotFoundError, ValidationError
from ..validator import validate_group, validate_run_settings
from ..helpers import format_timestamp, did_you_mean
from .utils import handle_exceptions, no_config_message


@click.group()
def group():
    """Run groups of tasks and list them.

    \b
    Examples:
      signalbox group run nightly   run the tasks of a group
      signalbox group list          each group, its schedule and tasks
    """
    pass


@group.command(name="run")
@click.argument("name")
@handle_exceptions
def group_run(name):
    """Run a group of tasks."""
    if run_group(name) not in ("success", "skipped"):
        sys.exit(1)


def run_group(name):
    """Run a group, record its result and print the run table. Used by `group run` and `run-overdue`.

    Returns:
        str: the group status: 'success', 'partial', 'failed' or 'skipped'

    Raises:
        GroupNotFoundError: if there is no group with this name
        ValidationError: if the group or a task it refers to is not valid (recorded as failed)
    """
    config = load_config()
    group_item = find_entry(config, "groups", name)
    if not group_item:
        groups = [g.get("name") for g in config.get("groups", []) if isinstance(g, dict)]
        raise GroupNotFoundError(name, did_you_mean(name, groups))
    errors = validate_group(group_item) + validate_run_settings()
    known_tasks = {t.get("name") for t in config.get("tasks", []) if isinstance(t, dict)}
    task_refs = group_item.get("tasks") if isinstance(group_item.get("tasks"), list) else []
    errors += [
        f"Group '{name}' references non-existent task '{t}'.{did_you_mean(t, known_tasks)}".rstrip(".")
        for t in task_refs
        if isinstance(t, str) and t not in known_tasks
    ]
    if errors:
        # Record the failed attempt: otherwise the tray keeps the last good status and only later shows "overdue"
        group_source_file = config["_group_sources"].get(name)
        if group_source_file:
            save_group_runtime_state(name, group_source_file, format_timestamp(datetime.now()), "failed", 0, 0, 0)
        raise ValidationError("; ".join(errors))
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
    from ..cli_output import print_run_table

    # Run all tasks in a single call so parallel/serial semantics are correct.
    if execution_mode == "parallel":
        results = run_group_parallel(task_names, config)
    else:
        results = run_group_serial(task_names, config, stop_on_error)
    end_time = datetime.now()
    execution_time = (end_time - start_time).total_seconds()
    tasks_total = len(task_names)
    tasks_successful = sum(1 for r in results if r["status"] == "success")
    # Tasks skipped on purpose (run_if, overlap, platform) do not count for or against the group;
    # tasks skipped by stop_on_error do, since an earlier task failed
    counted = tasks_total - sum(1 for r in results if r.get("skip") == "condition")
    if tasks_total and not counted:
        group_status = "skipped"
    elif tasks_successful == counted:
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

    print_run_table(results)
    skipped = sum(1 for r in results if r.get("skip") == "condition")
    summary = f"{tasks_successful} of {counted} tasks succeeded" + (f", {skipped} skipped" if skipped else "")
    click.echo(f"Group {name}: {group_status} ({summary})")
    return group_status


@group.command(name="list")
def group_list():
    """List all available groups and their tasks."""
    config = load_config()
    groups = config.get("groups", [])
    if not groups:
        click.echo(no_config_message(config) or "No groups defined.")
        return
    from ..cli_output import print_group_list_table

    group_rows = []
    for group_item in groups:
        try:
            group_rows.append(
                {
                    "name": group_item.get("name", ""),
                    "description": group_item.get("description", ""),
                    "schedule": describe(get_schedule_string(group_item)) if "schedule" in group_item else "",
                    "execution": group_item.get("execution", "serial"),
                    "stop_on_error": group_item.get("stop_on_error", False),
                    "tasks": group_item.get("tasks", []),
                }
            )
        except Exception as e:
            click.echo(
                f"[CONFIG ERROR] Unexpected error in the group configuration: {e}. Group: {group_item}", err=True
            )
    print_group_list_table(group_rows)
