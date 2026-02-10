from rich.table import Table
from rich.console import Console

def print_task_run_table(results):
    """
    Print a table of task run results using rich.
    results: list of dicts with keys: name, status, log_file, error
    """
    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("TASK", style="bold", overflow="fold")
    table.add_column("STATUS", style="bold", justify="center")
    table.add_column("LOG FILE", style="dim", overflow="fold")
    table.add_column("ERROR", style="red", overflow="fold")

    for row in results:
        status_style = {
            "success": "green",
            "ok": "green",
            "failed": "red",
            "fail": "red",
            "error": "red",
        }.get(row["status"].lower(), "yellow")
        table.add_row(
            row["name"],
            f"[{status_style}]{row['status']}[/{status_style}]",
            row["log_file"],
            row["error"] if row["error"] else "",
        )
    console.print(table)

def print_group_run_table(results):
    """
    Print a table of group run results using rich.
    results: list of dicts with keys: name, status, log_file, error
    """
    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("TASK", style="bold", overflow="fold")
    table.add_column("STATUS", style="bold", justify="center")
    table.add_column("LOG FILE", style="dim", overflow="fold")
    table.add_column("ERROR", style="red", overflow="fold")

    for row in results:
        status_style = {
            "success": "green",
            "ok": "green",
            "failed": "red",
            "fail": "red",
            "error": "red",
        }.get(row["status"].lower(), "yellow")
        table.add_row(
            row["name"],
            f"[{status_style}]{row['status']}[/{status_style}]",
            row["log_file"],
            row["error"] if row["error"] else "",
        )
    console.print(table)
