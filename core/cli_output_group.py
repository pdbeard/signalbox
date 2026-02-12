from rich.table import Table
from rich.console import Console

def get_schedule_display(schedule):
    """Extract schedule string for display.
    
    Handles both formats:
    - String: "0 * * * *"
    - Dict: {"cron": "0 * * * *"}
    """
    if isinstance(schedule, dict):
        return schedule.get("cron", "")
    return schedule or ""

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
        schedule = get_schedule_display(row["schedule"])
        execution = row["execution"]
        if row["stop_on_error"]:
            execution += ", stop_on_error"
        # Ensure tasks is a list of strings
        tasks_list = row["tasks"]
        if isinstance(tasks_list, list):
            # Filter out non-strings and convert to strings
            tasks = ", ".join([str(t) for t in tasks_list if isinstance(t, (str, int, float))])
        else:
            tasks = str(tasks_list) if tasks_list else ""
        table.add_row(
            row["name"],
            row["description"],
            schedule,
            execution,
            tasks,
        )
    console.print(table)
