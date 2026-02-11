# CLI command definitions for signalbox
import importlib.metadata
from datetime import datetime
import os
import sys
import shutil
import yaml
from functools import wraps
import click

from .config import load_config, get_config_value, load_global_config, _default_config_manager
from .executor import run_task, run_group_parallel, run_group_serial
from .runtime import save_group_runtime_state, load_runtime_state, merge_config_with_runtime_state
from . import log_manager
from . import validator
from . import exporters
from . import notifications
from . import alerts
from .exceptions import SignalboxError, TaskNotFoundError, GroupNotFoundError, ValidationError, ConfigurationError
from .helpers import format_timestamp, parse_timestamp
def handle_exceptions(func):
    """Decorator to handle exceptions consistently across CLI commands with proper exit codes."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            click.echo("\nInterrupted by user", err=True)
            sys.exit(130)
        except (ValidationError, ConfigurationError, FileNotFoundError) as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(2)
        except PermissionError as e:
            click.echo(f"Permission Denied: {e}", err=True)
            sys.exit(126)
        except SignalboxError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(e.exit_code)
        except Exception as e:
            click.echo(f"Unexpected error: {str(e)}", err=True)
            if os.getenv("DEBUG"):
                import traceback
                traceback.print_exc()
            sys.exit(1)

    return wrapper

@click.group(
    help="""
Signalbox - Task automation and monitoring.

\b
PRIMARY COMMANDS:
  task            Manage and run tasks (run, list)
  group           Manage and run task groups
  log             View and manage execution logs
  config          Configuration management
  
\b
QUICK COMMANDS (shortcuts):
  run NAME        Run a task
  list            List all tasks
  validate        Validate configuration

\b
Run 'signalbox COMMAND --help' for more information on a command.
"""
)
@click.option("--config", "-c", "config_path", default=None, help="Path to custom signalbox.yaml config file")
@click.version_option(importlib.metadata.version("signalbox"), "--version", "-V", message="%(version)s")
def cli(config_path):
    """Signalbox - Task execution control and monitoring."""
    if config_path:
        # Set config home to the directory containing the custom config file
        import os

        config_dir = os.path.dirname(os.path.abspath(config_path))
        _default_config_manager._config_home = config_dir
        # Optionally, reset cached config so it reloads
        _default_config_manager._global_config = None


# ============================================================================
# Command Groups
# ============================================================================

@cli.group()
def task():
    """
    Manage and run tasks.
    
    \b
    Commands:
      run [NAME|--all]   Run a single task or all tasks
      list               List all configured tasks with status
    """
    pass


@cli.group()
def group():
    """
    Manage and run task groups.
    
    \b
    Commands:
      run NAME    Run a group of tasks
      list        List all configured groups
    """
    pass


@cli.group()
def log():
    """
    View and manage execution logs.
    
    \b
    Commands:
      list [OPTIONS]     List all task execution logs with filters
      show TASK          Show the latest log for a task
      tail TASK          Follow log output in real-time
      history TASK       Show all historical logs for a task
      clear [OPTIONS]    Clear logs for tasks
    """
    pass


@cli.group()
def config():
    """
    Configuration management.
    
    \b
    Commands:
      show [KEY]    Show configuration (all or specific setting)
      validate      Validate configuration files
      path          Show configuration directory path
    """
    pass


@cli.group()
def runtime():
    """Runtime state management commands."""
    pass


# ============================================================================
# Root-Level Commands
# ============================================================================


@cli.command()
def init():
    """Initialize signalbox configuration in the appropriate config directory (XDG/SIGNALBOX_HOME supported)"""
    from .config import find_config_home
    config_dir = find_config_home()

    if os.path.exists(config_dir):
        click.echo(f"Configuration directory already exists: {config_dir}")
        if not click.confirm("Do you want to reinitialize (this will backup existing config)?"):
            return
        # Backup existing config
        backup_dir = f"{config_dir}.backup.{format_timestamp(datetime.now())}"
        shutil.move(config_dir, backup_dir)
        click.echo(f"Backed up existing config to: {backup_dir}")

    # Find the installed package's config templates
    # The config directory is core/config, which is a sibling to this file's directory
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    template_config = os.path.join(current_file_dir, "config")
    
    # If not found there, try using pkg_resources (older installations)
    if not os.path.exists(template_config):
        try:
            import pkg_resources
            package_path = pkg_resources.resource_filename("core", "config")
            if os.path.exists(package_path):
                template_config = package_path
        except Exception:
            pass

    if os.path.exists(template_config):
        # Copy the entire config directory
        shutil.copytree(template_config, os.path.join(config_dir, "config"))
        click.echo(f"✓ Created configuration directory: {config_dir}")
        click.echo(f"✓ Copied default config from: {template_config}")
    else:
        # Config directory not found - this should not happen in a proper installation
        click.echo(f"ERROR: Could not find config templates at: {template_config}", err=True)
        click.echo("This may indicate an incomplete package installation.", err=True)
        click.echo("Please reinstall signalbox or file an issue at:", err=True)
        click.echo("  https://github.com/pdbeard/signalbox/issues", err=True)
        sys.exit(1)

    # Create logs and runtime directories
    os.makedirs(os.path.join(config_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(config_dir, "runtime/tasks"), exist_ok=True)
    os.makedirs(os.path.join(config_dir, "runtime/groups"), exist_ok=True)

    click.echo(f"✓ Created logs directory: {config_dir}/logs")
    click.echo(f"✓ Created runtime directory: {config_dir}/runtime")
    click.echo()
    click.echo("Signalbox initialized successfully!")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Review configuration: {config_dir}/config/signalbox.yaml")
    click.echo(f"  2. Add your tasks: {config_dir}/config/tasks/")
    click.echo(f"  3. Run: signalbox list")
    click.echo("SECURITY: Signalbox executes commands with full shell access.")
    click.echo("   Only use trusted YAML files. See SECURITY.md for details.")
    click.echo("   You can now run signalbox from any directory!")


# Root-level shortcuts for frequently used commands
@cli.command(name="run")
@click.argument("name")
@handle_exceptions
def run_shortcut(name):
    """Run a task (shortcut to 'task run <name>')."""
    os.environ["SIGNALBOX_SUPPRESS_CONFIG_WARNINGS"] = "1"
    config = load_config(suppress_warnings=True)
    run_task(name, config)


@cli.command(name="list")
def list_shortcut():
    """List all tasks (shortcut to 'task list')."""
    from click import Context
    ctx = Context(task_list)
    ctx.invoke(task_list)


@cli.command(name="validate")
@handle_exceptions
def validate_shortcut():
    """Validate configuration (shortcut to 'config validate')."""
    # Will be defined later in the file, so we import it dynamically
    from click import Context
    ctx = Context(config_validate)
    ctx.invoke(config_validate)


# ============================================================================
# Task Commands
# ============================================================================

@task.command(name="list")
def task_list():
    """List all tasks and their status, grouped by config file."""
    config = load_config()
    runtime_state = load_runtime_state()
    config = merge_config_with_runtime_state(config, runtime_state)

    date_format = get_config_value("display.date_format", "%Y-%m-%d %H:%M:%S")
    # Group tasks by their source file
    task_sources = config.get("_task_sources", {})
    tasks_by_file = {}
    for task in config["tasks"]:
        source = task_sources.get(task.get("name"), "<unknown source>")
        tasks_by_file.setdefault(source, []).append(task)

    import os

    # Flatten all tasks with their source file for a single table
    from core.cli_output import print_task_list_table
    all_rows = []
    for source_file, tasks in tasks_by_file.items():
        file_name = os.path.basename(source_file)
        for task in tasks:
            try:
                name = task.get("name", "")
                status = task.get("last_status", "not run")
                last_run = task.get("last_run", "")
                description = task.get("description", "")
                source = file_name
                # Format last run
                if last_run:
                    try:
                        timestamp_str = last_run.replace(".log", "")
                        dt = parse_timestamp(timestamp_str)
                        last_run_str = dt.strftime(date_format)
                    except Exception:
                        last_run_str = last_run
                else:
                    last_run_str = ""
                all_rows.append({
                    "name": name,
                    "status": status,
                    "last_run": last_run_str,
                    "description": description,
                    "source": source,
                })
            except KeyError as e:
                click.echo(f"[CONFIG ERROR] Task entry missing required field: {e}. Offending task: {task}", err=True)
            except Exception as e:
                click.echo(f"[CONFIG ERROR] Unexpected error in task config: {e}. Offending task: {task}", err=True)
    print_task_list_table(all_rows)


@task.command(name="run")
@click.argument("name", required=False)
@click.option("--all", "run_all_tasks", is_flag=True, help="Run all tasks")
@handle_exceptions
def task_run(name, run_all_tasks):
    """Run a single task or all tasks."""
    if run_all_tasks:
        import os
        os.environ["SIGNALBOX_SUPPRESS_CONFIG_WARNINGS"] = "1"
        config = load_config(suppress_warnings=True)
        click.echo("Running all tasks...")
        from core.cli_output_run import print_task_run_table
        results = []
        for task_item in config["tasks"]:
            name = task_item["name"]
            log_file = ""
            error = ""
            try:
                click.echo(f"Running {name}...")
                success = run_task(name, config)
                status = "success" if success else "failed"
                # Find log file
                log_dir = config.get("paths", {}).get("log_dir", "logs")
                log_path = os.path.join(log_dir, name)
                log_files = sorted([f for f in os.listdir(log_path) if f.endswith(".log")], reverse=True)
                log_file = log_files[0] if log_files else ""
            except SignalboxError as e:
                status = "failed"
                error = str(e)
            except Exception as e:
                status = "failed"
                error = str(e)
            results.append({
                "name": name,
                "status": status,
                "log_file": log_file,
                "error": error,
            })
        print_task_run_table(results)
        failed_tasks = [r["name"] for r in results if r["status"] != "success"]
        if failed_tasks:
            click.echo(f"\n{len(failed_tasks)} task(s) failed: {', '.join(failed_tasks)}", err=True)
            sys.exit(1)
        else:
            click.echo("\nAll tasks completed successfully")
            sys.exit(0)
    elif name:
        import os
        os.environ["SIGNALBOX_SUPPRESS_CONFIG_WARNINGS"] = "1"
        config = load_config(suppress_warnings=True)
        success = run_task(name, config)
        if not success:
            sys.exit(1)
    else:
        click.echo("Error: Provide task name or use --all", err=True)
        sys.exit(2)


# ============================================================================
# Group Commands
# ============================================================================


@group.command(name="run")
@click.argument("name")
@handle_exceptions
def group_run(name):
    """Run a group of tasks."""
    config = load_config()
    groups = config.get("groups", [])
    group = next((g for g in groups if g["name"] == name), None)
    if not group:
        raise GroupNotFoundError(name)
    execution_mode = group.get("execution", "serial")
    stop_on_error = group.get("stop_on_error", False)
    click.echo(f"Running group {name}: {group['description']}")
    if execution_mode == "parallel":
        click.echo(f"Execution mode: parallel")
    else:
        click.echo(f"Execution mode: serial (stop_on_error: {stop_on_error})")
    task_names = group["tasks"]
    start_time = datetime.now()
    timestamp = format_timestamp(start_time)
    from core.cli_output_run import print_group_run_table
    results = []
    for task_name in task_names:
        log_file = ""
        error = ""
        try:
            click.echo(f"Running {task_name}...")
            if execution_mode == "parallel":
                success = run_group_parallel([task_name], config)
            else:
                success = run_group_serial([task_name], config, stop_on_error)
            status = "success" if success else "failed"
            log_dir = config.get("paths", {}).get("log_dir", "logs")
            log_path = os.path.join(log_dir, task_name)
            log_files = sorted([f for f in os.listdir(log_path) if f.endswith(".log")], reverse=True)
            log_file = log_files[0] if log_files else ""
        except SignalboxError as e:
            status = "failed"
            error = str(e)
        except Exception as e:
            status = "failed"
            error = str(e)
        results.append({
            "name": task_name,
            "status": status,
            "log_file": log_file,
            "error": error,
        })
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


# ============================================================================
# Log Commands
# ============================================================================

@log.command(name="show")
@click.argument("name")
@handle_exceptions
def log_show(name):
    """Show the latest log for a task."""
    config = load_config()
    task = next((t for t in config["tasks"] if t["name"] == name), None)
    if not task:
        raise TaskNotFoundError(name)

    log_path, exists = log_manager.get_latest_log(name)
    if not exists:
        click.echo("No logs found")
        return

    # Use display settings from global config
    include_paths = get_config_value("display.include_paths", False)
    show_colors = get_config_value("display.colors", True)

    if include_paths:
        click.echo(f"Log file: {log_path}")
        click.echo("=" * 50)

    content = log_manager.read_log_content(log_path)
    formatted_lines = log_manager.format_log_with_colors(content, show_colors)

    for line, color in formatted_lines:
        if color:
            click.echo(click.style(line, fg=color))
        else:
            click.echo(line)


@log.command(name="history")
@click.argument("name")
@handle_exceptions
def log_history_cmd(name):
    """Show all historical log files for a task."""
    config = load_config()
    task = next((t for t in config["tasks"] if t["name"] == name), None)
    if not task:
        raise TaskNotFoundError(name)

    log_info, exists = log_manager.get_log_history(name)
    if not exists:
        click.echo("No history found")
        return

    # Use display settings from global config
    include_paths = get_config_value("display.include_paths", False)
    date_format = get_config_value("display.date_format", "%Y-%m-%d %H:%M:%S")

    task_log_dir = log_manager.get_task_log_dir(name)
    path_info = f" ({task_log_dir})" if include_paths else ""
    click.echo(f"Log history for {name}{path_info}:")

    for filename, mtime in log_info:
        time_str = datetime.fromtimestamp(mtime).strftime(date_format)
        click.echo(f"  {filename} - {time_str}")


@log.command(name="list")
@click.option("--task", help="Filter to specific task")
@click.option("--status", type=click.Choice(["success", "failed"]), help="Filter by status")
@click.option("--failed", is_flag=True, help="Shortcut for --status failed")
@click.option("--success", is_flag=True, help="Shortcut for --status success")
@click.option("--since", help="Show logs since date (YYYY-MM-DD)")
@click.option("--until", help="Show logs until date (YYYY-MM-DD)")
@click.option("--today", is_flag=True, help="Show only today's logs")
@click.option("--last", "limit", type=int, default=50, help="Show last N runs (default: 50)")
@handle_exceptions
def log_list_cmd(task, status, failed, success, since, until, today, limit):
    """List all task execution logs with filters."""
    from datetime import datetime, timedelta
    
    # Get all logs
    logs = log_manager.get_all_log_files()
    
    if not logs:
        click.echo("No logs found")
        return
    
    # Apply status shortcuts
    if failed:
        status = "failed"
    elif success:
        status = "success"
    
    # Parse date filters
    since_dt = None
    until_dt = None
    
    if today:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        since_dt = today_start
    elif since:
        try:
            since_dt = datetime.strptime(since, "%Y-%m-%d")
        except ValueError:
            click.echo(f"Error: Invalid date format for --since: {since}. Use YYYY-MM-DD", err=True)
            sys.exit(2)
    
    if until:
        try:
            until_dt = datetime.strptime(until, "%Y-%m-%d")
            until_dt = until_dt.replace(hour=23, minute=59, second=59)
        except ValueError:
            click.echo(f"Error: Invalid date format for --until: {until}. Use YYYY-MM-DD", err=True)
            sys.exit(2)
    
    # Filter logs
    filtered_logs = log_manager.filter_logs(
        logs, 
        task=task, 
        status=status, 
        since=since_dt, 
        until=until_dt,
        limit=limit
    )
    
    if not filtered_logs:
        click.echo("No logs found matching filters")
        return
    
    # Table output using rich
    from core.cli_output_tables import print_log_list_table
    date_format = get_config_value("display.date_format", "%Y-%m-%d %H:%M:%S")
    log_rows = []
    for log in filtered_logs:
        try:
            log_rows.append({
                "task": log["task"],
                "status": log["metadata"]["status"],
                "timestamp": log["timestamp"].strftime(date_format),
                "log_file": log["log_file"],
            })
        except Exception as e:
            click.echo(f"[LOG ERROR] {e} in log: {log}", err=True)
    print_log_list_table(log_rows)
    click.echo(f"Total: {len(filtered_logs)} log(s)")


@log.command(name="tail")
@click.argument("name")
@click.option("-f", "--follow", is_flag=True, default=True, help="Follow log output (default)")
@click.option("-n", "--lines", type=int, default=10, help="Number of lines to show initially (default: 10)")
@handle_exceptions
def log_tail_cmd(name, follow, lines):
    """Follow log output in real-time (like tail -f)."""
    import time
    import subprocess
    
    config = load_config()
    task = next((t for t in config["tasks"] if t["name"] == name), None)
    if not task:
        raise TaskNotFoundError(name)
    
    log_path, exists = log_manager.get_latest_log(name)
    if not exists:
        click.echo(f"No logs found for task '{name}'")
        click.echo("Waiting for new logs...")
        
        # Wait for log file to appear
        task_log_dir = log_manager.get_task_log_dir(name)
        while not exists:
            time.sleep(0.5)
            log_path, exists = log_manager.get_latest_log(name)
    
    click.echo(f"Following log: {log_path}")
    click.echo("─" * 50)
    
    # Use tail -f on Unix-like systems
    if os.name != 'nt':  # Not Windows
        try:
            subprocess.run(["tail", f"-n{lines}", "-f", log_path])
        except KeyboardInterrupt:
            click.echo("\nStopped following log")
    else:
        # Simple Python implementation for cross-platform
        try:
            with open(log_path, 'r') as f:
                # Show last N lines
                lines_buffer = []
                for line in f:
                    lines_buffer.append(line)
                    if len(lines_buffer) > lines:
                        lines_buffer.pop(0)
                
                for line in lines_buffer:
                    click.echo(line, nl=False)
                
                # Follow new content
                if follow:
                    while True:
                        line = f.readline()
                        if line:
                            click.echo(line, nl=False)
                        else:
                            time.sleep(0.1)
        except KeyboardInterrupt:
            click.echo("\nStopped following log")


@log.command(name="clear")
@click.option("--task", "task_name", help="Clear logs for specific task")
@click.option("--all", "clear_all", is_flag=True, help="Clear all logs for all tasks")
@handle_exceptions
def log_clear(task_name, clear_all):
    """Clear logs for a specific task or all tasks."""
    if clear_all:
        if log_manager.clear_all_logs():
            click.echo("Cleared all logs")
        else:
            click.echo("No logs directory found")
    elif task_name:
        config = load_config()
        task = next((t for t in config["tasks"] if t["name"] == task_name), None)
        if not task:
            raise TaskNotFoundError(task_name)
        if log_manager.clear_task_logs(task_name):
            click.echo(f"Cleared logs for {task_name}")
        else:
            click.echo(f"No logs found for {task_name}")
    else:
        click.echo("Error: Provide --task NAME or --all", err=True)
        sys.exit(2)


# ============================================================================
# Config Commands
# ============================================================================


@group.command(name="list")
def group_list():
    """List all available groups and their tasks."""
    config = load_config()
    groups = config.get("groups", [])
    if not groups:
        click.echo("No groups defined.")
        return
    from core.cli_output_group import print_group_list_table
    group_rows = []
    for group in groups:
        try:
            group_rows.append({
                "name": group.get("name", ""),
                "description": group.get("description", ""),
                "schedule": group.get("schedule", ""),
                "execution": group.get("execution", "serial"),
                "stop_on_error": group.get("stop_on_error", False),
                "tasks": group.get("tasks", []),
            })
        except KeyError as e:
            click.echo(f"[CONFIG ERROR] Group entry missing required field: {e}. Offending group: {group}", err=True)
        except Exception as e:
            click.echo(f"[CONFIG ERROR] Unexpected error in group config: {e}. Offending group: {group}", err=True)
    print_group_list_table(group_rows)


@config.command(name="show")
@click.argument("key", required=False)
def config_show(key):
    """Show global configuration or specific setting (use dot notation)."""
    if key:
        # Show specific setting
        value = get_config_value(key)
        if value is None:
            click.echo(f"Setting '{key}' not found")
        else:
            click.echo(f"{key}: {value}")
    else:
        # Show all config
        global_config = load_global_config()

        if not global_config:
            click.echo("No global configuration found (config/signalbox.yaml)")
            return

        click.echo("Global Configuration (config/signalbox.yaml):\n")
        click.echo(yaml.dump(global_config, default_flow_style=False, sort_keys=False))


@config.command(name="path")
def config_path():
    """Show the configuration directory path."""
    from .config import find_config_home
    config_dir = find_config_home()
    click.echo(config_dir)


@cli.command()
def list_schedules():
    """List all scheduled groups with their cron schedules."""
    config = load_config()
    groups = config.get("groups", [])
    scheduled = [g for g in groups if "schedule" in g]

    if not scheduled:
        click.echo("No scheduled groups defined.")
        return

    from core.cli_output_tables import print_schedule_list_table
    schedule_rows = []
    for group in scheduled:
        schedule_rows.append({
            "group": group.get('name', ''),
            "schedule": group.get('schedule', ''),
            "description": group.get('description', 'N/A'),
            "task_count": len(group.get('tasks', [])),
            "tasks": ", ".join(group.get('tasks', [])),
        })
    print_schedule_list_table(schedule_rows)


@cli.command()
@click.argument("group_name")
@click.option("--user", is_flag=True, help="Generate for user systemd (not system-wide)")
def export_systemd(group_name, user):
    """Generate systemd service and timer files for a scheduled group."""
    config = load_config()
    groups = config.get("groups", [])
    group = next((g for g in groups if g["name"] == group_name), None)

    result = exporters.export_systemd(group, group_name)

    if not result.success:
        click.echo(f"Error: {result.error}")
        return

    # Show generated files
    for file_path in result.files:
        click.echo(f"✓ Generated {file_path}")

    # Show installation instructions
    click.echo("")
    instructions = exporters.get_systemd_install_instructions(result.files[0], result.files[1], group_name, user)
    for instruction in instructions:
        click.echo(instruction)


@cli.command()
@click.argument("group_name")
def export_cron(group_name):
    """Generate crontab entry for a scheduled group."""
    config = load_config()
    groups = config.get("groups", [])
    group = next((g for g in groups if g["name"] == group_name), None)

    result = exporters.export_cron(group, group_name)

    if not result.success:
        click.echo(f"Error: {result.error}")
        return

    # Show generated file
    click.echo(f"✓ Generated {result.files[0]}")
    click.echo("")

    # Show installation instructions
    instructions = exporters.get_cron_install_instructions(result.files[0], result.cron_entry, group)
    for instruction in instructions:
        click.echo(instruction)


@config.command(name="validate")
@handle_exceptions
def config_validate():
    """Validate configuration files for errors."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    
    console = Console()
    result = validator.validate_configuration()

    # Show which files are being validated
    if result.files_used:
        files_text = "\n".join([f"  • {f}" for f in result.files_used])
        console.print(Panel(files_text, title="[bold cyan]Validating Configuration Files[/bold cyan]", 
                           border_style="cyan", box=box.ROUNDED))

    # Show errors
    if result.errors:
        error_text = ""
        for error in result.errors:
            if not error.strip():
                error_text += "\n"
            elif error.strip().endswith(".yaml") or error.strip().startswith(
                ("Task Config File", "Group Config File")
            ):
                error_text += f"[bold red]{error}[/bold red]\n"
            else:
                error_text += f"  [red]✗[/red] {error}\n"
        console.print(Panel(error_text.rstrip(), title="[bold red]Errors Found[/bold red]", 
                           border_style="red", box=box.ROUNDED))

    # Show warnings
    if result.warnings:
        warning_text = "\n".join([f"  [yellow]⚠[/yellow] {w}" for w in result.warnings])
        console.print(Panel(warning_text, title="[bold yellow]Warnings[/bold yellow]", 
                           border_style="yellow", box=box.ROUNDED))

        strict_mode = get_config_value("validation.strict", False)
        if strict_mode:
            console.print("\n[red]Validation failed (strict mode enabled)[/red]")
            sys.exit(2)

    # Show success message
    if not result.has_issues:
        console.print(f"\n[bold green]✓ Configuration is valid[/bold green]\n")
    elif not result.errors:
        console.print(f"\n[bold green]✓ No errors found[/bold green] [dim](warnings only)[/dim]\n")

    # Show summary
    if result.config and not result.has_issues:
        summary = validator.get_validation_summary(result)
        
        summary_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        summary_table.add_column("Item", style="cyan")
        summary_table.add_column("Value", style="bold white")
        
        summary_table.add_row("Tasks", str(summary.get('tasks', 0)))
        summary_table.add_row("Groups", str(summary.get('groups', 0)))
        summary_table.add_row("Scheduled groups", str(summary.get('scheduled_groups', 0)))
        
        if "default_timeout" in summary:
            summary_table.add_row("Default timeout", f"{summary['default_timeout']}s")
            log_limit = summary.get("default_log_limit", {})
            summary_table.add_row("Default log limit", 
                                 f"{log_limit.get('type', 'count')} = {log_limit.get('value', 10)}")
        
        console.print(Panel(summary_table, title="[bold cyan]Summary[/bold cyan]", 
                           border_style="cyan", box=box.ROUNDED))

    # Exit with appropriate code if validation failed
    if not result.is_valid:
        sys.exit(2)


@cli.command()
@click.option("--title", default="Signalbox Test", help="Notification title")
@click.option("--message", default="This is a test notification from Signalbox", help="Notification message")
@click.option(
    "--urgency",
    type=click.Choice(["low", "normal", "critical"]),
    default="normal",
    help="Notification urgency level (Linux only)",
)
@handle_exceptions
def notify_test(title, message, urgency):
    """Send a test notification to verify notification system works."""
    import platform

    system = platform.system()
    click.echo(f"Sending test notification on {system}...")
    click.echo(f"Title: {title}")
    click.echo(f"Message: {message}")
    if system == "Linux":
        click.echo(f"Urgency: {urgency}")

    success = notifications.send_notification(title, message, urgency)

    if success:
        click.echo("✓ Notification sent successfully!")
    else:
        click.echo("✗ Failed to send notification. Check logs for details.", err=True)
        sys.exit(1)


@cli.command()
@click.argument("task_name", required=False)
@click.option("--severity", type=click.Choice(["info", "warning", "critical"]), help="Filter by severity")
@click.option("--days", type=int, help="Show alerts from last N days")
@handle_exceptions
def alerts_cmd(task_name, severity, days):
    """List recent alerts. Optionally filter by task name, severity, or time range."""

    # Load alerts with filters
    alert_list = alerts.load_alerts(task_name=task_name, severity=severity, max_days=days)

    if not alert_list:
        if task_name:
            click.echo(f"No alerts found for task '{task_name}'")
        else:
            click.echo("No alerts found")
        return

    # Display alerts
    date_format = get_config_value("display.date_format", "%Y-%m-%d %H:%M:%S")

    for alert in alert_list:
        try:
            timestamp_str = alert.get("timestamp", "")
            dt = parse_timestamp(timestamp_str)
            human_date = dt.strftime(date_format)
        except Exception:
            human_date = timestamp_str

        severity_str = alert.get("severity", "info")
        task = alert.get("task_name", "unknown")
        message = alert.get("message", "")

        # Color code by severity
        if severity_str == "critical":
            severity_label = click.style(severity_str, fg="red", bold=True)
        elif severity_str == "warning":
            severity_label = click.style(severity_str, fg="yellow")
        else:
            severity_label = click.style(severity_str, fg="blue")

        click.echo(f"[{human_date}] [{severity_label}] {task}: {message}")

    # Show summary
    click.echo(f"\nTotal alerts: {len(alert_list)}")


# Register the alerts command with the CLI group
cli.add_command(alerts_cmd, name="alerts")
