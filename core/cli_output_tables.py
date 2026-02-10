from rich.table import Table
from rich.console import Console

def print_log_list_table(log_rows):
    """
    Print a table of logs using rich.
    log_rows: list of dicts with keys: task, status, timestamp, log_file
    """
    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("TASK", style="bold", overflow="fold")
    table.add_column("STATUS", style="bold", justify="center")
    table.add_column("TIMESTAMP", style="dim", justify="center")
    table.add_column("LOG FILE", style="", overflow="fold")

    for row in log_rows:
        status_style = {
            "success": "green",
            "ok": "green",
            "failed": "red",
            "fail": "red",
            "error": "red",
        }.get(row["status"].lower(), "yellow")
        table.add_row(
            row["task"],
            f"[{status_style}]{row['status']}[/{status_style}]",
            row["timestamp"],
            row["log_file"],
        )
    console.print(table)

def print_schedule_list_table(schedule_rows):
    """
    Print a table of scheduled groups using rich.
    schedule_rows: list of dicts with keys: group, schedule, description, task_count, tasks
    """
    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("GROUP", style="bold", overflow="fold")
    table.add_column("SCHEDULE", style="", overflow="fold")
    table.add_column("DESCRIPTION", style="", overflow="fold")
    table.add_column("TASKS", style="dim", justify="center")
    table.add_column("TASK NAMES", style="", overflow="fold")

    for row in schedule_rows:
        table.add_row(
            row["group"],
            row["schedule"],
            row["description"],
            str(row["task_count"]),
            row["tasks"],
        )
    console.print(table)
