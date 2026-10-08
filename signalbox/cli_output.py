# Rich-based terminal output for signalbox CLI commands
from rich import box
from rich.console import Console
from rich.table import Table

STATUS_COLOURS = {
    "success": "green",
    "ok": "green",
    "failed": "red",
    "fail": "red",
    "error": "red",
}


def status_colour(status):
    """Return the rich colour for a status string (yellow for anything unrecognised)."""
    return STATUS_COLOURS.get(str(status).lower(), "yellow")


def status_markup(status):
    """Return a status string wrapped in its rich colour markup."""
    colour = status_colour(status)
    return f"[{colour}]{status}[/{colour}]"


def get_schedule_display(schedule):
    """Extract schedule string for display.

    Handles both formats:
    - String: "0 * * * *"
    - Dict: {"cron": "0 * * * *"}
    """
    if isinstance(schedule, dict):
        return schedule.get("cron", "")
    return schedule or ""


def _table(*columns, **kwargs):
    """Build a table with the standard header style; columns are (title, column kwargs) pairs."""
    table = Table(show_header=True, header_style="bold magenta", **kwargs)
    for title, options in columns:
        table.add_column(title, **options)
    return table


def print_task_list_table(task_rows):
    """
    Print a table of tasks using rich.
    task_rows: list of dicts with keys: name, status, last_run, description, source
    """
    table = _table(
        ("TASK", {"style": "bold", "overflow": "fold"}),
        ("STATUS", {"style": "bold", "justify": "center"}),
        ("LAST RUN", {"style": "dim", "justify": "center"}),
        ("DESCRIPTION", {"overflow": "fold"}),
        ("SOURCE", {"style": "dim", "overflow": "fold"}),
    )
    for row in task_rows:
        table.add_row(row["name"], status_markup(row["status"]), row["last_run"], row["description"], row["source"])
    Console().print(table)


def print_run_table(results):
    """
    Print a table of task run results (used by `task run --all` and `group run`).
    results: list of dicts with keys: name, status, log_file, error
    """
    table = _table(
        ("TASK", {"style": "bold", "overflow": "fold"}),
        ("STATUS", {"style": "bold", "justify": "center"}),
        ("LOG FILE", {"style": "dim", "overflow": "fold"}),
        ("ERROR", {"style": "red", "overflow": "fold"}),
    )
    for row in results:
        table.add_row(row["name"], status_markup(row["status"]), row["log_file"], row["error"] or "")
    Console().print(table)


def print_group_list_table(group_rows):
    """
    Print a table of groups using rich.
    group_rows: list of dicts with keys: name, description, schedule, execution, stop_on_error, tasks
    """
    table = _table(
        ("GROUP", {"style": "bold", "overflow": "fold"}),
        ("DESCRIPTION", {"overflow": "fold"}),
        ("SCHEDULE", {"style": "dim", "overflow": "fold"}),
        ("EXECUTION", {"justify": "center"}),
        ("TASKS", {"overflow": "fold"}),
    )
    for row in group_rows:
        execution = str(row["execution"])
        if row["stop_on_error"]:
            execution += ", stop_on_error"
        tasks_list = row["tasks"]
        if isinstance(tasks_list, list):
            tasks = ", ".join(str(t) for t in tasks_list if isinstance(t, (str, int, float)))
        else:
            tasks = str(tasks_list) if tasks_list else ""
        table.add_row(row["name"], row["description"], get_schedule_display(row["schedule"]), execution, tasks)
    Console().print(table)


def print_schedule_list_table(schedule_rows):
    """
    Print a table of scheduled groups using rich.
    schedule_rows: list of dicts with keys: group, schedule, description, task_count, tasks
    """
    table = _table(
        ("GROUP", {"style": "bold", "overflow": "fold"}),
        ("SCHEDULE", {"overflow": "fold"}),
        ("DESCRIPTION", {"overflow": "fold"}),
        ("TASKS", {"style": "dim", "justify": "center"}),
        ("TASK NAMES", {"overflow": "fold"}),
    )
    for row in schedule_rows:
        table.add_row(row["group"], row["schedule"], row["description"], str(row["task_count"]), row["tasks"])
    Console().print(table)


def print_log_list_table(log_rows):
    """
    Print a table of logs using rich.
    log_rows: list of dicts with keys: task, status, timestamp, preview
    """
    table = _table(
        ("TASK", {"style": "bold", "overflow": "fold"}),
        ("STATUS", {"style": "bold", "justify": "center"}),
        ("TIMESTAMP", {"style": "dim", "justify": "center"}),
        ("OUTPUT PREVIEW", {"overflow": "fold"}),
        box=box.SIMPLE_HEAD,
    )
    for row in log_rows:
        table.add_row(row["task"], status_markup(row["status"]), row["timestamp"], row.get("preview", ""))
    Console().print(table)


def print_log_list_verbose(log_rows, max_lines=20):
    """
    Print expanded log entries with truncated stdout below each header.
    log_rows: list of dicts with keys: task, status, timestamp, stdout, stderr
    """
    console = Console()
    for row in log_rows:
        status = row["status"]
        colour = status_colour(status)
        icon = "✓" if colour == "green" else "✗"

        console.print(
            f"[bold]{icon} {row['task']}[/bold]  " f"[{colour}]{status}[/{colour}]  " f"[dim]{row['timestamp']}[/dim]"
        )

        output = row.get("stdout", "").strip() or row.get("stderr", "").strip()
        if output:
            lines = output.splitlines()
            for line in lines[:max_lines]:
                console.print(f"  [dim]{line}[/dim]")
            remaining = len(lines) - max_lines
            if remaining > 0:
                console.print(
                    f"  [dim italic]… {remaining} more line(s) — "
                    f"run 'signalbox log show {row['task']}' to see all[/dim italic]"
                )
        else:
            console.print("  [dim italic](no output)[/dim italic]")

        console.print("")
