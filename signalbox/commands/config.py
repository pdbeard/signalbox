# Config commands: signalbox config show / path / check-permissions / validate
import os
import sys

import click
import yaml

from ..config import get_config_value, load_global_config, find_config_home
from .. import validator
from .utils import handle_exceptions


@click.group()
def config():
    """
    Configuration management.

    \b
    Commands:
      show [KEY]          Show configuration (all or specific setting)
      validate            Validate configuration files
      path                Show configuration directory path
      check-permissions   Check config and log directory permissions
    """
    pass


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
    click.echo(find_config_home())


@config.command(name="check-permissions")
def config_check_permissions():
    """Check that config and log directories have secure permissions.

    Warns if the config directory, task files, or log directory are readable
    or writable by users other than the owner. Config files should be treated
    as shell scripts — if they can be written by others, arbitrary commands
    can be injected into scheduled tasks.
    """
    config_home = find_config_home()
    log_dir = get_config_value("paths.log_dir", "logs")
    if not os.path.isabs(log_dir):
        log_dir = os.path.join(config_home, log_dir)

    issues = []

    def check_dir(path, label):
        if not os.path.exists(path):
            return
        mode = os.stat(path).st_mode & 0o777
        if mode & 0o077:
            issues.append(f"{label} is accessible by group/others: {path}  (current: {oct(mode)}, recommended: 0o700)")

    def check_file(path, label):
        if not os.path.exists(path):
            return
        mode = os.stat(path).st_mode & 0o777
        if mode & 0o022:
            issues.append(f"{label} is writable by group/others: {path}  (current: {oct(mode)}, recommended: 0o600)")

    check_dir(config_home, "Config home")
    check_dir(log_dir, "Log directory")

    tasks_dir = os.path.join(config_home, "config", "tasks")
    if os.path.exists(tasks_dir):
        for fname in os.listdir(tasks_dir):
            fpath = os.path.join(tasks_dir, fname)
            if os.path.isfile(fpath):
                check_file(fpath, f"Task file '{fname}'")

    groups_dir = os.path.join(config_home, "config", "groups")
    if os.path.exists(groups_dir):
        for fname in os.listdir(groups_dir):
            fpath = os.path.join(groups_dir, fname)
            if os.path.isfile(fpath):
                check_file(fpath, f"Group file '{fname}'")

    if issues:
        click.echo("Permission issues found:", err=True)
        for issue in issues:
            click.echo(f"  WARNING: {issue}", err=True)
        click.echo("\nRun: chmod 700 <directory>  or  chmod 600 <file>  to fix.", err=True)
        sys.exit(1)
    else:
        click.echo("All permission checks passed.")


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
        console.print(
            Panel(
                files_text,
                title="[bold cyan]Validating Configuration Files[/bold cyan]",
                border_style="cyan",
                box=box.ROUNDED,
            )
        )

    # Show errors
    if result.errors:
        error_text = ""
        for error in result.errors:
            if not error.strip():
                error_text += "\n"
            elif error.strip().endswith(".yaml") or error.strip().startswith(("Task Config File", "Group Config File")):
                error_text += f"[bold red]{error}[/bold red]\n"
            else:
                error_text += f"  [red]✗[/red] {error}\n"
        console.print(
            Panel(error_text.rstrip(), title="[bold red]Errors Found[/bold red]", border_style="red", box=box.ROUNDED)
        )

    # Show warnings
    if result.warnings:
        warning_text = "\n".join([f"  [yellow]⚠[/yellow] {w}" for w in result.warnings])
        console.print(
            Panel(warning_text, title="[bold yellow]Warnings[/bold yellow]", border_style="yellow", box=box.ROUNDED)
        )

        strict_mode = get_config_value("validation.strict", False)
        if strict_mode:
            console.print("\n[red]Validation failed (strict mode enabled)[/red]")
            sys.exit(2)

    # Show success message
    if not result.has_issues:
        console.print("\n[bold green]✓ Configuration is valid[/bold green]\n")
    elif not result.errors:
        console.print("\n[bold green]✓ No errors found[/bold green] [dim](warnings only)[/dim]\n")

    # Show summary
    if result.config and not result.has_issues:
        summary = validator.get_validation_summary(result)

        summary_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        summary_table.add_column("Item", style="cyan")
        summary_table.add_column("Value", style="bold white")

        summary_table.add_row("Tasks", str(summary.get("tasks", 0)))
        summary_table.add_row("Groups", str(summary.get("groups", 0)))
        summary_table.add_row("Scheduled groups", str(summary.get("scheduled_groups", 0)))

        if "default_timeout" in summary:
            summary_table.add_row("Default timeout", f"{summary['default_timeout']}s")
            log_limit = summary.get("default_log_limit", {})
            summary_table.add_row(
                "Default log limit", f"{log_limit.get('type', 'count')} = {log_limit.get('value', 10)}"
            )

        console.print(
            Panel(summary_table, title="[bold cyan]Summary[/bold cyan]", border_style="cyan", box=box.ROUNDED)
        )

    # Exit with appropriate code if validation failed
    if not result.is_valid:
        sys.exit(2)
