# Task and group execution logic for signalbox
#
# SECURITY NOTE: This module executes shell commands with shell=True to support
# pipes, redirection, and complex bash scripts. Commands are executed with the
# full permissions of the user running signalbox.
#
# Configuration files MUST be trusted. See SECURITY.md for details.
#
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import click

from .config import get_config_value
from .runtime import save_task_runtime_state
from .log_manager import ensure_log_dir, get_log_path, write_execution_log, rotate_logs
from .exceptions import TaskNotFoundError, ExecutionError, ExecutionTimeoutError, ValidationError
from . import notifications
from . import alerts
from .helpers import format_timestamp
from .validator import validate_task


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
        result = subprocess.run(task["command"], shell=True, capture_output=True, text=True, timeout=timeout)
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
    # subprocess.run kills the child with SIGKILL on timeout, so -9 is the honest return code
    write_execution_log(log_file, task["command"], -9, stdout, stderr)
    rotate_logs(task)

    task_source_file = config["_task_sources"].get(name)
    if task_source_file:
        save_task_runtime_state(name, task_source_file, timestamp, "failed")
    task["last_status"] = "failed"
    task["last_run"] = timestamp


def _post_execution(name, task, result, log_file, timestamp, config):
    """Handle all post-execution concerns: logging, alerts, notifications, log rotation, runtime state."""
    write_execution_log(log_file, task["command"], result.returncode, result.stdout, result.stderr)

    # Check for alert patterns in output
    combined_output = result.stdout + "\n" + result.stderr
    triggered_alerts = alerts.check_alert_patterns(name, task, combined_output)

    # Save and optionally notify for each triggered alert
    if triggered_alerts:
        global_alerts_enabled = get_config_value("alerts.notifications.enabled", True)
        global_on_failure_only = get_config_value("alerts.notifications.on_failure_only", True)

        for alert in triggered_alerts:
            alerts.save_alert(name, alert)

            severity_label = alert["severity"].upper()
            click.echo(f"  [{severity_label}] {alert['message']}")

            alert_notify = alert.get("notify")
            if alert_notify is False:
                continue
            alerts_enabled = alert_notify if alert_notify is not None else global_alerts_enabled

            if alerts_enabled:
                alert_on_failure_only = alert.get("on_failure_only")
                on_failure_only = alert_on_failure_only if alert_on_failure_only is not None else global_on_failure_only
                alert_severity = alert.get("severity", "info")
                if on_failure_only and alert_severity == "info":
                    continue
                alert_title = alert.get("title") or f"Alert: {name}"
                notifications.send_notification(
                    title=alert_title,
                    message=alert["message"],
                    urgency="critical" if alert_severity == "critical" else "normal",
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
        ValidationError: If the task definition is invalid (e.g. missing 'command')
        ExecutionTimeoutError: If task execution times out
        ExecutionError: If task execution fails for any other reason
    """
    task = _find_task(name, config)
    errors = validate_task(task)
    if errors:
        raise ValidationError("; ".join(errors))
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
