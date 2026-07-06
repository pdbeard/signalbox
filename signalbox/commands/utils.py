# Shared helpers for CLI command modules
import os
import sys
from functools import wraps

import click

from ..exceptions import SignalboxError, ValidationError, ConfigurationError


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


def print_run_output_preview(stdout, stderr, task_name, max_lines=20):
    """Print truncated stdout (and stderr if present) after a task run."""
    output = stdout.strip()
    err = stderr.strip()

    if not output and not err:
        return

    click.echo("")
    if output:
        lines = output.splitlines()
        for line in lines[:max_lines]:
            click.echo(f"  {line}")
        if len(lines) > max_lines:
            click.echo(f"  ... {len(lines) - max_lines} more line(s) — run 'signalbox log show {task_name}' to see all")
    if err:
        for line in err.splitlines()[:5]:
            click.echo(click.style(f"  {line}", fg="red"))
    click.echo("")
