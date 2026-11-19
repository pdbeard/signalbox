# Root CLI group for signalbox: registers command groups and shortcuts
import importlib.metadata
import os

import click

from .config import set_config_home
from .commands.task import task, task_list, task_run
from .commands.group import group
from .commands.log import log
from .commands.config import config, config_validate
from .commands.misc import (
    init,
    list_schedules,
    export_systemd,
    export_cron,
    notify_test,
    alerts_cmd,
    status,
    run_overdue,
)

# The commands in the help, by what people want to do (click lists them alphabetically otherwise)
HELP_SECTIONS = (
    ("Get started", ("init", "validate")),
    ("Run", ("run", "task", "group", "run-overdue")),
    ("Check", ("status", "list", "log", "alerts")),
    ("Schedule", ("list-schedules", "export-cron", "export-systemd")),
    ("Configure", ("config", "notify-test")),
)


class SectionedGroup(click.Group):
    """A click group whose help lists the commands in HELP_SECTIONS, not alphabetically."""

    def format_commands(self, ctx, formatter):
        listed = set()
        for title, names in HELP_SECTIONS + (("Other", tuple(sorted(self.commands))),):
            rows = []
            for name in names:
                command = self.commands.get(name)
                if command is None or command.hidden or name in listed:
                    continue
                listed.add(name)
                rows.append((name, command.get_short_help_str(limit=formatter.width)))
            if rows:
                with formatter.section(title):
                    formatter.write_dl(rows)


@click.group(
    cls=SectionedGroup,
    help="Signalbox runs your shell tasks, keeps a log of each run, and tells you when one fails or does not run.",
    epilog="""\b
Examples:
  signalbox init                           make the configuration
  signalbox run hello                      run a task and see its output
  signalbox status                         is everything OK?
  signalbox log show hello                 the output of the latest run
  signalbox export-cron --all --install    schedule all groups with cron

\b
Run 'signalbox COMMAND --help' for the options of a command.
Tutorial: https://github.com/pdbeard/signalbox/blob/main/documentation/QUICKSTART.md
""",
)
@click.option(
    "--config",
    "-c",
    "config_path",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to a signalbox.yaml inside a config/ directory (<home>/config/signalbox.yaml)",
)
@click.version_option(importlib.metadata.version("signalbox"), "--version", "-V", message="%(version)s")
def cli(config_path):
    """Signalbox - Task execution control and monitoring."""
    if config_path:
        # The home is the directory containing config/signalbox.yaml; any other
        # location would silently load a different file.
        config_path = os.path.abspath(config_path)
        config_dir = os.path.dirname(config_path)
        if os.path.basename(config_dir) != "config" or os.path.basename(config_path) != "signalbox.yaml":
            raise click.BadParameter(
                f"expected <home>/config/signalbox.yaml, got {config_path}", param_hint="'--config'"
            )
        set_config_home(os.path.dirname(config_dir))


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
cli.add_command(status)
cli.add_command(run_overdue)


# Root-level shortcuts for frequently used commands
@cli.command(name="run", short_help="Run a task and show its output.")
@click.argument("name")
@click.option("--quiet", "-q", is_flag=True, help="Do not show the output preview")
@click.pass_context
def run_shortcut(ctx, name, quiet):
    """Run a task and show its output (same as: signalbox task run NAME)."""
    ctx.invoke(task_run, name=name, run_all_tasks=False, quiet=quiet)


@cli.command(name="list", short_help="List the tasks, their status and last run.")
@click.pass_context
def list_shortcut(ctx):
    """List the tasks: status and last run (same as: signalbox task list)."""
    ctx.invoke(task_list)


@cli.command(name="validate", short_help="Find errors in the configuration.")
@click.pass_context
def validate_shortcut(ctx):
    """Find errors in the configuration (same as: signalbox config validate)."""
    ctx.invoke(config_validate)
