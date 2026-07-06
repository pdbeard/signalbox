# Root CLI group for signalbox: registers command groups and shortcuts
import importlib.metadata
import os

import click

from .config import set_config_home
from .commands.task import task, task_list, task_run
from .commands.group import group
from .commands.log import log
from .commands.config import config, config_validate
from .commands.misc import init, list_schedules, export_systemd, export_cron, notify_test, alerts_cmd


@click.group(help="""
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
""")
@click.option("--config", "-c", "config_path", default=None, help="Path to custom signalbox.yaml config file")
@click.version_option(importlib.metadata.version("signalbox"), "--version", "-V", message="%(version)s")
def cli(config_path):
    """Signalbox - Task execution control and monitoring."""
    if config_path:
        # Config home is the directory that contains config/signalbox.yaml.
        # If the given file lives in a directory named "config", use its
        # parent so resolve_path("config/signalbox.yaml") finds the file.
        config_dir = os.path.dirname(os.path.abspath(config_path))
        if os.path.basename(config_dir) == "config":
            config_dir = os.path.dirname(config_dir)
        set_config_home(config_dir)


# Command groups
cli.add_command(task)
cli.add_command(group)
cli.add_command(log)
cli.add_command(config)

# Root-level commands
cli.add_command(init)
cli.add_command(list_schedules)
cli.add_command(export_systemd)
cli.add_command(export_cron)
cli.add_command(notify_test)
cli.add_command(alerts_cmd, name="alerts")


# Root-level shortcuts for frequently used commands
@cli.command(name="run")
@click.argument("name")
@click.option("--quiet", "-q", is_flag=True, help="Suppress inline output preview")
@click.pass_context
def run_shortcut(ctx, name, quiet):
    """Run a task (shortcut for 'task run NAME')."""
    ctx.invoke(task_run, name=name, run_all_tasks=False, quiet=quiet)


@cli.command(name="list")
@click.pass_context
def list_shortcut(ctx):
    """List all tasks (shortcut for 'task list')."""
    ctx.invoke(task_list)


@cli.command(name="validate")
@click.pass_context
def validate_shortcut(ctx):
    """Validate configuration (shortcut for 'config validate')."""
    ctx.invoke(config_validate)
