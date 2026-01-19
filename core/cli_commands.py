# CLI command definitions for signalbox
import click
from datetime import datetime
import os
import sys
import shutil
import yaml
from functools import wraps

from .config import load_config, get_config_value, load_global_config
from .executor import run_script, run_group_parallel, run_group_serial
from .runtime import save_group_runtime_state, load_runtime_state, merge_config_with_runtime_state
from . import log_manager
from . import validator
from . import exporters
from . import notifications
from .exceptions import SignalboxError, ScriptNotFoundError, GroupNotFoundError
from .helpers import format_timestamp, parse_timestamp


def handle_exceptions(func):
    """Decorator to handle exceptions consistently across CLI commands."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SignalboxError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(e.exit_code)
        except Exception as e:
            click.echo(f"Unexpected error: {str(e)}", err=True)
            sys.exit(1)

    return wrapper


@click.group()
def cli():
    """signalbox - Script execution control and monitoring."""
    pass


@cli.command()
def init():
    """Initialize signalbox configuration in ~/.config/signalbox/"""
    config_dir = os.path.expanduser("~/.config/signalbox")

    if os.path.exists(config_dir):
        click.echo(f"Configuration directory already exists: {config_dir}")
        if not click.confirm("Do you want to reinitialize (this will backup existing config)?"):
            return
        # Backup existing config
        backup_dir = f"{config_dir}.backup.{format_timestamp(datetime.now())}"
        shutil.move(config_dir, backup_dir)
        click.echo(f"Backed up existing config to: {backup_dir}")

    # Find the installed package's config templates
    # Try to locate the original config from the package installation
    try:
        import pkg_resources

        package_path = pkg_resources.resource_filename("signalbox", "")
        template_config = os.path.join(os.path.dirname(package_path), "config")

        # If not found, try relative to this file (for development)
        if not os.path.exists(template_config):
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            template_config = os.path.join(os.path.dirname(current_file_dir), "config")
    except Exception:
        # Fallback to relative path from current module
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        template_config = os.path.join(os.path.dirname(current_file_dir), "config")

    if os.path.exists(template_config):
        # Copy the entire config directory
        shutil.copytree(template_config, os.path.join(config_dir, "config"))
        click.echo(f"✓ Created configuration directory: {config_dir}")
        click.echo(f"✓ Copied default config from: {template_config}")
    else:
        # Create minimal structure if template not found
        os.makedirs(config_dir, exist_ok=True)
        os.makedirs(os.path.join(config_dir, "config/scripts"), exist_ok=True)
        os.makedirs(os.path.join(config_dir, "config/groups"), exist_ok=True)

        # Create minimal signalbox.yaml
        default_config = {
            "default_log_limit": {"type": "count", "value": 10},
            "paths": {"log_dir": "logs", "scripts_file": "config/scripts", "groups_file": "config/groups"},
            "execution": {
                "default_timeout": 300,
                "capture_stdout": True,
                "capture_stderr": True,
                "max_parallel_workers": 5,
            },
            "logging": {"timestamp_format": "%Y%m%d_%H%M%S_%f"},
            "display": {"date_format": "%Y-%m-%d %H:%M:%S"},
            "notifications": {
                "enabled": True,
                "on_failure_only": True,
                "show_failed_names": True,
            },
        }

        with open(os.path.join(config_dir, "config/signalbox.yaml"), "w") as f:
            yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)

        # Create example script
        example_script = {
            "scripts": [{"name": "hello", "command": 'echo "Hello from signalbox!"', "description": "Example script"}]
        }
        with open(os.path.join(config_dir, "config/scripts/example.yaml"), "w") as f:
            yaml.dump(example_script, f, default_flow_style=False, sort_keys=False)

        click.echo(f"✓ Created minimal configuration: {config_dir}")

    # Create logs and runtime directories
    os.makedirs(os.path.join(config_dir, "logs"), exist_ok=True)
    os.makedirs(os.path.join(config_dir, "runtime/scripts"), exist_ok=True)
    os.makedirs(os.path.join(config_dir, "runtime/groups"), exist_ok=True)

    click.echo(f"✓ Created logs directory: {config_dir}/logs")
    click.echo(f"✓ Created runtime directory: {config_dir}/runtime")
    click.echo()
    click.echo("Signalbox initialized successfully!")
    click.echo()
    click.echo("Next steps:")
    click.echo(f"  1. Review configuration: {config_dir}/config/signalbox.yaml")
    click.echo(f"  2. Add your scripts: {config_dir}/config/scripts/")
    click.echo(f"  3. Run: signalbox list")
    click.echo("SECURITY: Signalbox executes commands with full shell access.")
    click.echo("   Only use trusted YAML files. See SECURITY.md for details.")
    click.echo("   You can now run signalbox from any directory!")


@cli.command()
def list():
    """List all scripts and their status, grouped by config file."""
    config = load_config()
    runtime_state = load_runtime_state()
    config = merge_config_with_runtime_state(config, runtime_state)

    date_format = get_config_value("display.date_format", "%Y-%m-%d %H:%M:%S")
    # Group scripts by their source file
    script_sources = config.get("_script_sources", {})
    scripts_by_file = {}
    for script in config["scripts"]:
        source = script_sources.get(script.get("name"), "<unknown source>")
        scripts_by_file.setdefault(source, []).append(script)

    import os
    for source_file, scripts in scripts_by_file.items():
        file_name = os.path.basename(source_file)
        click.echo(f"\n=== {file_name} ===")
        for script in scripts:
            try:
                status = script.get("last_status", "not run")
                last_run = script.get("last_run", "")
                name = script["name"]
                description = script["description"]
                # Color for status
                if status.lower() in ("success", "ok"):
                    status_str = click.style(status, fg="green", bold=True)
                elif status.lower() in ("failed", "fail", "error"):
                    status_str = click.style(status, fg="red", bold=True)
                else:
                    status_str = click.style(status, fg="yellow")
                if last_run:
                    try:
                        timestamp_str = last_run.replace(".log", "")
                        dt = parse_timestamp(timestamp_str)
                        human_date = dt.strftime(date_format)
                        click.echo(f"{name}: {status_str} ({human_date}) - {description}")
                    except Exception:
                        click.echo(f"{name}: {status_str} ({last_run}) - {description}")
                else:
                    click.echo(f"{name}: {status_str} - {description}")
            except KeyError as e:
                label = click.style("[CONFIG ERROR]", fg="red", bold=True)
                msg = f" Script entry missing required field: {e}. Check your scripts YAML files. Offending script: {script}"
                click.echo(f"{label}{msg}", err=True)
            except Exception as e:
                label = click.style("[CONFIG ERROR]", fg="red", bold=True)
                msg = f" Unexpected error in script config: {e}. Offending script: {script}"
                click.echo(f"{label}{msg}", err=True)


@cli.command()
@click.argument("name")
@handle_exceptions
def run(name):
    """Run a specific script by name."""
    config = load_config()
    run_script(name, config)


@cli.command()
@handle_exceptions
def run_all():
    """Run all scripts."""
    config = load_config()
    click.echo("Running all scripts...")
    for script in config["scripts"]:
        click.echo(f"Running {script['name']}...")
        try:
            run_script(script["name"], config)
        except SignalboxError as e:
            click.echo(f"Error: {e.message}", err=True)
    click.echo("All scripts executed.")


@cli.command("run-group")
@click.argument("name")
@handle_exceptions
def run_group(name):
    """Run a group of scripts."""
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
    script_names = group["scripts"]
    start_time = datetime.now()
    timestamp = format_timestamp(start_time)
    if execution_mode == "parallel":
        scripts_successful = run_group_parallel(script_names, config)
    else:
        scripts_successful = run_group_serial(script_names, config, stop_on_error)
    end_time = datetime.now()
    execution_time = (end_time - start_time).total_seconds()
    scripts_total = len(script_names)
    if scripts_successful == scripts_total:
        group_status = "success"
    elif scripts_successful > 0:
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
            scripts_total=scripts_total,
            scripts_successful=scripts_successful,
        )

    click.echo(f"Group {name} executed.")


@cli.command()
@click.argument("name")
@handle_exceptions
def logs(name):
    """Show the latest log for a script."""
    config = load_config()
    script = next((s for s in config["scripts"] if s["name"] == name), None)
    if not script:
        raise ScriptNotFoundError(name)

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


@cli.command()
@click.argument("name")
@handle_exceptions
def history(name):
    """Show all log files for a script."""
    config = load_config()
    script = next((s for s in config["scripts"] if s["name"] == name), None)
    if not script:
        raise ScriptNotFoundError(name)

    log_info, exists = log_manager.get_log_history(name)
    if not exists:
        click.echo("No history found")
        return

    # Use display settings from global config
    include_paths = get_config_value("display.include_paths", False)
    date_format = get_config_value("display.date_format", "%Y-%m-%d %H:%M:%S")

    script_log_dir = log_manager.get_script_log_dir(name)
    path_info = f" ({script_log_dir})" if include_paths else ""
    click.echo(f"History for {name}{path_info}:")

    for filename, mtime in log_info:
        time_str = datetime.fromtimestamp(mtime).strftime(date_format)
        click.echo(f"  {filename} - {time_str}")


@cli.command()
@click.argument("name")
@handle_exceptions
def clear_logs(name):
    """Clear all logs for a specific script."""
    config = load_config()
    script = next((s for s in config["scripts"] if s["name"] == name), None)
    if not script:
        raise ScriptNotFoundError(name)

    if log_manager.clear_script_logs(name):
        click.echo(f"Cleared logs for {name}")
    else:
        click.echo(f"No logs found for {name}")


@cli.command()
def clear_all_logs():
    """Clear all logs for all scripts."""
    if log_manager.clear_all_logs():
        click.echo("Cleared all logs")
    else:
        click.echo("No logs directory found")


@cli.command()
def list_groups():
    """List all available groups and their scripts."""
    config = load_config()
    groups = config.get("groups", [])
    if not groups:
        click.echo("No groups defined.")
        return
    for group in groups:
        try:
            schedule_info = f" [scheduled: {group['schedule']}]" if "schedule" in group else ""
            execution_mode = group.get("execution", "serial")
            stop_on_error = group.get("stop_on_error", False)

            # Build execution info
            exec_info = f" [execution: {execution_mode}"
            if execution_mode == "serial" and stop_on_error:
                exec_info += ", stop_on_error"
            exec_info += "]"

            click.echo(f"Group: {group['name']} - {group.get('description', '')}{schedule_info}{exec_info}")
            click.echo("  Scripts:")
            for script_name in group.get("scripts", []):
                click.echo(f"    - {script_name}")
            click.echo("")
        except KeyError as e:
            label = click.style("[CONFIG ERROR]", fg="red", bold=True)
            msg = f" Group entry missing required field: {e}. Offending group: {group}"
            click.echo(f"{label}{msg}", err=True)
        except Exception as e:
            label = click.style("[CONFIG ERROR]", fg="red", bold=True)
            msg = f" Unexpected error in group config: {e}. Offending group: {group}"
            click.echo(f"{label}{msg}", err=True)


@cli.command()
def show_config():
    """Show global configuration settings."""
    global_config = load_global_config()

    if not global_config:
        click.echo("No global configuration found (config/signalbox.yaml)")
        return

    click.echo("Global Configuration (config/signalbox.yaml):\n")
    click.echo(yaml.dump(global_config, default_flow_style=False, sort_keys=False))


@cli.command()
@click.argument("key")
def get_setting(key):
    """Get a specific configuration value (use dot notation, e.g., 'execution.default_timeout')."""
    value = get_config_value(key)
    if value is None:
        click.echo(f"Setting '{key}' not found")
    else:
        click.echo(f"{key}: {value}")


@cli.command()
def list_schedules():
    """List all scheduled groups with their cron schedules."""
    config = load_config()
    groups = config.get("groups", [])
    scheduled = [g for g in groups if "schedule" in g]

    if not scheduled:
        click.echo("No scheduled groups defined.")
        return

    click.echo("Scheduled Groups:")
    for group in scheduled:
        script_count = len(group.get("scripts", []))
        click.echo(f"\n  {group['name']}")
        click.echo(f"    Schedule: {group['schedule']}")
        click.echo(f"    Description: {group.get('description', 'N/A')}")
        click.echo(f"    Scripts: {script_count}")
        for script_name in group.get("scripts", []):
            click.echo(f"      - {script_name}")


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


@cli.command()
@handle_exceptions
def validate():
    """Validate configuration files for errors."""
    result = validator.validate_configuration()

    # Show which files are being validated
    if result.files_used:
        click.echo(f"Validating: {', '.join(result.files_used)}\n")

    # Show errors
    if result.errors:
        click.echo("Errors found:")
        for error in result.errors:
            if not error.strip():
                click.echo()
            elif error.strip().endswith(".yaml") or error.strip().startswith(("Script Config File", "Group Config File")):
                click.echo(error)
            else:
                click.echo(f" - {error}")

    # Show warnings
    if result.warnings:
        click.echo("\nWarnings:")
        for warning in result.warnings:
            click.echo(f"{warning}")

        strict_mode = get_config_value("validation.strict", False)
        if strict_mode:
            click.echo("\nValidation failed (strict mode enabled)")
            sys.exit(5)

    # Show success message
    if not result.has_issues:
        click.echo("✓ Configuration is valid")
    elif not result.errors:
        click.echo("\n✓ No errors found (warnings only)")

    # Show summary
    if result.config and not result.has_issues:
        summary = validator.get_validation_summary(result)
        click.echo(f"\nSummary:")
        click.echo(f"  Scripts: {summary.get('scripts', 0)}")
        click.echo(f"  Groups: {summary.get('groups', 0)}")
        click.echo(f"  Scheduled groups: {summary.get('scheduled_groups', 0)}")

        if "default_timeout" in summary:
            click.echo(f"  Default timeout: {summary['default_timeout']}s")
            log_limit = summary.get("default_log_limit", {})
            click.echo(f"  Default log limit: {log_limit.get('type', 'count')} = {log_limit.get('value', 10)}")

    # Exit with appropriate code if validation failed
    if not result.is_valid:
        sys.exit(5)


@cli.command()
@click.option(
    "--title",
    default="Signalbox Test",
    help="Notification title"
)
@click.option(
    "--message",
    default="This is a test notification from Signalbox",
    help="Notification message"
)
@click.option(
    "--urgency",
    type=click.Choice(["low", "normal", "critical"]),
    default="normal",
    help="Notification urgency level (Linux only)"
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
