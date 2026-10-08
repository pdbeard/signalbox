# Task and group execution logic for signalbox
#
# SECURITY NOTE: This module executes shell commands with shell=True to support
# pipes, redirection, and complex bash scripts. Commands are executed with the
# full permissions of the user running signalbox.
#
# Configuration files MUST be trusted. See SECURITY.md for details.
#
import os
import signal
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import click

from .config import get_config_value, find_config_home
from .runtime import save_task_runtime_state
from .log_manager import ensure_log_dir, get_log_path, write_execution_log, rotate_logs
from .exceptions import TaskNotFoundError, ExecutionError, ExecutionTimeoutError, ValidationError, ConfigurationError
from . import notifications
from . import alerts
from .helpers import format_timestamp
from .validator import validate_task_for_run

# After a timeout kill, how long to wait for the pipes to close before giving up on the output
KILL_GRACE_SECONDS = 5


def _kill_process_group(proc):
    """SIGKILL every process in the task's process group (the shell and anything it started)."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_command(command, timeout=None, cwd=None):
    """Run a shell command the way signalbox runs every task.

    - The command gets its own session/process group, so a timeout (or Ctrl+C)
      kills everything it started, not just the shell.
    - stdin is /dev/null: a command that prompts fails fast instead of hanging
      invisibly (its output is captured) until the timeout.
    - cwd is explicit, so manual and scheduled runs behave the same.

    Returns:
        subprocess.CompletedProcess with text stdout/stderr

    Raises:
        subprocess.TimeoutExpired: With whatever output was captured before the kill
    """
    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc)
        try:
            # Retrying communicate() keeps the output read so far
            stdout, stderr = proc.communicate(timeout=KILL_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            # Something escaped the process group (e.g. daemonized) and still holds the pipes
            proc.stdout.close()
            proc.stderr.close()
            proc.wait()
            stdout, stderr = "", ""
        raise subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
    except BaseException:
        # The task is in its own session, so Ctrl+C no longer reaches it directly
        _kill_process_group(proc)
        proc.wait()
        raise
    return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)


def resolve_task_cwd(task):
    """Working directory for a task: its 'cwd' (relative to the signalbox home), or the home itself."""
    home = find_config_home()
    cwd = task.get("cwd")
    if not cwd:
        return home
    return os.path.join(home, os.path.expanduser(cwd))


def _find_task(name, config):
    """Find a task in the config by name.

    Raises:
        TaskNotFoundError: If no task with the given name exists in config.
    """
    task = next((t for t in config["tasks"] if isinstance(t, dict) and t.get("name") == name), None)
    if not task:
        raise TaskNotFoundError(name)
    return task


def _execute(task, name, config):
    """Run the task subprocess and return (result, log_file, timestamp).

    Handles timeout resolution and log path preparation. A task may override
    the global execution.default_timeout with its own 'timeout' field
    (in seconds, 0 = no timeout).

    Raises:
        ExecutionTimeoutError: If the subprocess exceeds the configured timeout.
    """
    timeout = task.get("timeout", get_config_value("execution.default_timeout", 300))
    # Security: Enforce minimum timeout to prevent DOS via infinite hangs
    min_timeout = get_config_value("execution.min_timeout", 1)
    if timeout == 0:
        timeout = None
    elif timeout < min_timeout:
        click.echo(f"Warning: Timeout {timeout}s is below minimum {min_timeout}s, using minimum", err=True)
        timeout = min_timeout

    ensure_log_dir(name)
    timestamp = format_timestamp(datetime.now())
    log_file = get_log_path(name, timestamp)

    try:
        result = run_command(task["command"], timeout=timeout, cwd=resolve_task_cwd(task))
    except subprocess.TimeoutExpired as e:
        _record_timeout(name, task, e, log_file, timestamp, config)
        raise ExecutionTimeoutError(name, timeout)

    return result, log_file, timestamp


def _as_text(output):
    """Normalize partial output from TimeoutExpired, which may be bytes, str, or None."""
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output


def _record_timeout(name, task, error, log_file, timestamp, config):
    """Write a log and mark the task failed so a timeout is visible in logs and the tray."""
    stdout = _as_text(error.stdout)
    stderr = _as_text(error.stderr) + f"\n[TIMED OUT after {error.timeout}s]"
    # run_command kills the process group with SIGKILL on timeout, so -9 is the honest return code
    write_execution_log(log_file, task["command"], -9, stdout, stderr)
    rotate_logs(task)

    task_source_file = config["_task_sources"].get(name)
    if task_source_file:
        save_task_runtime_state(name, task_source_file, timestamp, "failed")
    task["last_status"] = "failed"
    task["last_run"] = timestamp


def _should_notify(name, alert):
    """Decide whether a triggered alert sends a desktop notification.

    Per-alert 'notify' / 'on_failure_only' override the global settings
    (on_failure_only skips info-severity alerts). An alert that already
    notified for the same task and pattern within
    alerts.notifications.cooldown_minutes is recorded but not re-sent, so a
    task that runs every few minutes doesn't notify on every run.
    """
    notify = alert.get("notify")
    if notify is None:
        notify = get_config_value("alerts.notifications.enabled", True)
    if not notify:
        return False

    on_failure_only = alert.get("on_failure_only")
    if on_failure_only is None:
        on_failure_only = get_config_value("alerts.notifications.on_failure_only", True)
    if on_failure_only and alert.get("severity", "info") == "info":
        return False

    cooldown = get_config_value("alerts.notifications.cooldown_minutes", 60)
    return not (cooldown and alerts.notified_within(name, alert["pattern"], cooldown))


def _post_execution(name, task, result, log_file, timestamp, config):
    """Handle all post-execution concerns: logging, alerts, notifications, log rotation, runtime state."""
    write_execution_log(log_file, task["command"], result.returncode, result.stdout, result.stderr)

    # Check for alert patterns in output
    combined_output = result.stdout + "\n" + result.stderr
    triggered_alerts = alerts.check_alert_patterns(name, task, combined_output)

    # Save and optionally notify for each triggered alert
    for alert in triggered_alerts:
        alert["notified"] = _should_notify(name, alert)
        alerts.save_alert(name, alert)
        click.echo(f"  [{alert['severity'].upper()}] {alert['message']}")
        if alert["notified"]:
            notifications.send_notification(
                title=alert.get("title") or f"Alert: {name}",
                message=alert["message"],
                urgency="critical" if alert.get("severity") == "critical" else "normal",
            )

    rotate_logs(task)

    retention = get_config_value("alerts.retention", {})
    alerts.prune_alerts(
        name,
        max_days=retention.get("max_days", 30),
        max_entries=retention.get("max_entries", 1000),
        per_severity=retention.get("per_severity"),
    )

    status = "success" if result.returncode == 0 else "failed"
    click.echo(f"Task {name} {status}. Log: {log_file}")

    task_source_file = config["_task_sources"].get(name)
    if task_source_file:
        save_task_runtime_state(name, task_source_file, timestamp, status)

    task["last_status"] = status
    task["last_run"] = timestamp


def run_task(name, config):
    """Execute a single task and log the results.

    Args:
        name: Name of the task to run
        config: Full configuration dict containing tasks

    Returns:
        bool: True if task executed successfully (exit code 0), False otherwise

    Raises:
        TaskNotFoundError: If task not found in configuration
        ValidationError: If the task can't be run (e.g. missing 'command')
        ConfigurationError: If the task's working directory does not exist
        ExecutionTimeoutError: If task execution times out
        ExecutionError: If task execution fails for any other reason
    """
    task = _find_task(name, config)
    errors = validate_task_for_run(task)
    if errors:
        raise ValidationError("; ".join(errors))
    cwd = resolve_task_cwd(task)
    if not os.path.isdir(cwd):
        raise ConfigurationError(f"Working directory for task '{name}' does not exist: {cwd}")
    try:
        result, log_file, timestamp = _execute(task, name, config)
        _post_execution(name, task, result, log_file, timestamp, config)
        return result.returncode == 0
    except (ExecutionTimeoutError, TaskNotFoundError):
        raise
    except Exception as e:
        raise ExecutionError(name, str(e))


def _run_group_task(task_name, config):
    """Run one task of a group, converting exceptions into a failed result."""
    click.echo("")  # Add a blank line before each group task execution output
    click.echo(f"Running {task_name}...")
    try:
        success = run_task(task_name, config)
        return {"name": task_name, "status": "success" if success else "failed", "error": ""}
    except Exception as e:
        message = e.message if hasattr(e, "message") else str(e)
        click.echo(f"Error: {message}")
        return {"name": task_name, "status": "failed", "error": message}


def _notify_group_result(results, config):
    """Send the group summary notification for a list of task results."""
    ran = [r for r in results if r["status"] != "skipped"]
    failed_names = [r["name"] for r in ran if r["status"] != "success"]
    passed = len(ran) - len(failed_names)
    notifications.notify_execution_result(
        total=len(ran),
        passed=passed,
        failed=len(failed_names),
        context="tasks",
        failed_names=failed_names or None,
        config=config,
    )


def run_group_parallel(task_names, config):
    """Execute multiple tasks in parallel.

    Args:
            task_names: List of task names to execute
            config: Full configuration dict

    Returns:
            list: One dict per task, in task_names order, with keys
                  'name', 'status' ('success' or 'failed') and 'error'
    """
    max_workers = get_config_value("execution.max_parallel_workers", 5)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_run_group_task, name, config) for name in task_names]
        results = [future.result() for future in futures]

    # Print summary
    click.echo("\nParallel execution summary:")
    success_count = sum(1 for r in results if r["status"] == "success")
    click.echo(f"  Completed: {len(results)}/{len(task_names)}")
    click.echo(f"  Successful: {success_count}/{len(results)}")
    if success_count < len(results):
        failed_names = [r["name"] for r in results if r["status"] != "success"]
        click.echo(f"  Failed: {', '.join(failed_names)}")

    _notify_group_result(results, config)
    return results


def run_group_serial(task_names, config, stop_on_error):
    """Execute multiple tasks sequentially.

    Args:
            task_names: List of task names to execute
            config: Full configuration dict
            stop_on_error: If True, stop execution when a task fails

    Returns:
            list: One dict per task, in task_names order, with keys 'name',
                  'status' ('success', 'failed', or 'skipped' for tasks not run
                  because of stop_on_error) and 'error'
    """
    results = []
    for task_name in task_names:
        if results and results[-1]["status"] != "success" and stop_on_error:
            results.append({"name": task_name, "status": "skipped", "error": ""})
            continue
        result = _run_group_task(task_name, config)
        results.append(result)
        if result["status"] != "success" and stop_on_error:
            click.echo(f"⚠️  Task {task_name} failed. Stopping group execution (stop_on_error=true)")

    _notify_group_result(results, config)
    return results
