from rich.table import Table
from rich.console import Console

def print_group_list_table(group_rows):
    """
    Print a table of groups using rich.
    group_rows: list of dicts with keys: name, description, schedule, execution, stop_on_error, tasks
    """
    console = Console()
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("GROUP", style="bold", overflow="fold")
    table.add_column("DESCRIPTION", style="", overflow="fold")
    table.add_column("SCHEDULE", style="dim", overflow="fold")
    table.add_column("EXECUTION", style="", justify="center")
    table.add_column("TASKS", style="", overflow="fold")

    for row in group_rows:
        schedule = row["schedule"] if row["schedule"] else ""
        execution = row["execution"]
        if row["stop_on_error"]:
            execution += ", stop_on_error"
        tasks = ", ".join(row["tasks"])
        table.add_row(
            row["name"],
            row["description"],
            schedule,
            execution,
            tasks,
        )
    console.print(table)
