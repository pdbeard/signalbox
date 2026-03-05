from rich.table import Table
from rich.console import Console
from rich import box
import click


def print_log_list_table(log_rows):
    """
    Print a table of logs using rich.
    log_rows: list of dicts with keys: task, status, timestamp, preview
    """
    console = Console()
    table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE_HEAD)
    table.add_column("TASK", style="bold", overflow="fold")
    table.add_column("STATUS", style="bold", justify="center")
    table.add_column("TIMESTAMP", style="dim", justify="center")
    table.add_column("OUTPUT PREVIEW", style="", overflow="fold")

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
            row.get("preview", ""),
        )
    console.print(table)


def print_log_list_verbose(log_rows, max_lines=20):
    """
    Print expanded log entries with truncated stdout below each header.
    log_rows: list of dicts with keys: task, status, timestamp, stdout, stderr
    """
    console = Console()
    status_colours = {
        "success": "green", "ok": "green",
        "failed": "red", "fail": "red", "error": "red",
    }

    for row in log_rows:
        status = row["status"]
        colour = status_colours.get(status.lower(), "yellow")
        icon = "✓" if colour == "green" else "✗"

        console.print(
            f"[bold]{icon} {row['task']}[/bold]  "
            f"[{colour}]{status}[/{colour}]  "
            f"[dim]{row['timestamp']}[/dim]"
        )

        stdout = row.get("stdout", "").strip()
        stderr = row.get("stderr", "").strip()

        output = stdout or stderr
        if output:
            lines = output.splitlines()
            shown = lines[:max_lines]
            remaining = len(lines) - max_lines
            for line in shown:
                console.print(f"  [dim]{line}[/dim]")
            if remaining > 0:
                console.print(
                    f"  [dim italic]… {remaining} more line(s) — "
                    f"run 'signalbox log show {row['task']}' to see all[/dim italic]"
                )
        else:
            console.print("  [dim italic](no output)[/dim italic]")

        console.print("")


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
