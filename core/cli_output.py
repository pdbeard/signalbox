from rich.table import Table
from rich.console import Console

def print_task_list_table(task_rows):
    """
    Print a table of tasks using rich.
    task_rows: list of dicts with keys: name, status, last_run, description, source
    """
    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("TASK", style="bold", overflow="fold")
    table.add_column("STATUS", style="bold", justify="center")
    table.add_column("LAST RUN", style="dim", justify="center")
    table.add_column("DESCRIPTION", style="", overflow="fold")
    table.add_column("SOURCE", style="dim", overflow="fold")

    for row in task_rows:
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
            row["last_run"],
            row["description"],
            row["source"],
        )
    console.print(table)
