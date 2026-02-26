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
from concurrent.futures import ThreadPoolExecutor, as_completed
import click

from .config import get_config_value
from .runtime import save_task_runtime_state
from .log_manager import ensure_log_dir, get_log_path, write_execution_log, rotate_logs
from .exceptions import TaskNotFoundError, ExecutionError, ExecutionTimeoutError
from . import notifications
from . import alerts
from .helpers import format_timestamp


def _find_task(name, config):
    """Find a task in the config by name.

    Raises:
        TaskNotFoundError: If no task with the given name exists in config.
    """
    task = next((s for s in config["tasks"] if s["name"] == name), None)
    if not task:
        raise TaskNotFoundError(name)
    return task


def _execute(task, name):
    """Run the task subprocess and return (result, log_file, timestamp).

    Handles timeout resolution and log path preparation.

    Raises:
        ExecutionTimeoutError: If the subprocess exceeds the configured timeout.
    """
    timeout = get_config_value("execution.default_timeout", 300)
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
    except subprocess.TimeoutExpired:
        raise ExecutionTimeoutError(name, timeout)

    return result, log_file, timestamp


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
        ExecutionTimeoutError: If task execution times out
        ExecutionError: If task execution fails for any other reason
    """
    task = _find_task(name, config)
    try:
        result, log_file, timestamp = _execute(task, name)
        _post_execution(name, task, result, log_file, timestamp, config)
        return result.returncode == 0
    except (ExecutionTimeoutError, TaskNotFoundError):
        raise
    except Exception as e:
        raise ExecutionError(name, str(e))


def run_group_parallel(task_names, config):
    """Execute multiple tasks in parallel.

    Args:
            task_names: List of task names to execute
            config: Full configuration dict

    Returns:
            int: Number of tasks that executed successfully
    """
    max_workers = get_config_value("execution.max_parallel_workers", 5)

    def run_task_wrapper(task_name):
        """Wrapper for parallel execution that catches exceptions."""
        try:
            click.echo("")  # Add a blank line before each group task execution output
            click.echo(f"Running {task_name}...")
            success = run_task(task_name, config)
            return (task_name, success, None)
        except Exception as e:
            click.echo(f"Error: {e.message if hasattr(e, 'message') else str(e)}")
            return (task_name, False, str(e))

    # Execute tasks in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_task_wrapper, name): name for name in task_names}
        results = []
        for future in as_completed(futures):
            task_name, success, error = future.result()
            results.append((task_name, success, error))

    # Print summary
    click.echo("\nParallel execution summary:")
    success_count = sum(1 for _, success, _ in results if success)
    click.echo(f"  Completed: {len(results)}/{len(task_names)}")
    click.echo(f"  Successful: {success_count}/{len(results)}")

    failed_names = None
    if success_count < len(results):
        failed_names = [name for name, success, _ in results if not success]
        click.echo(f"  Failed: {', '.join(failed_names)}")

    # Send notification
    failed_count = len(results) - success_count
    notifications.notify_execution_result(
        total=len(results),
        passed=success_count,
        failed=failed_count,
        context="tasks",
        failed_names=failed_names,
        config=config,
    )

    return success_count


def run_group_serial(task_names, config, stop_on_error):
    """Execute multiple tasks sequentially.

    Args:
            task_names: List of task names to execute
            config: Full configuration dict
            stop_on_error: If True, stop execution when a task fails

    Returns:
            int: Number of tasks that executed successfully
    """
    success_count = 0
    failed_names = []

    for task_name in task_names:
        try:
            click.echo("")  # Add a blank line before each group task execution output
            click.echo(f"Running {task_name}...")
            success = run_task(task_name, config)

            if success:
                success_count += 1
            else:
                failed_names.append(task_name)
                if stop_on_error:
                    click.echo(f"⚠️  Task {task_name} failed. Stopping group execution (stop_on_error=true)")
                    break
        except Exception as e:
            click.echo(f"Error: {e.message if hasattr(e, 'message') else str(e)}")
            failed_names.append(task_name)
            if stop_on_error:
                click.echo(f"⚠️  Stopping group execution (stop_on_error=true)")
                break

    # Send notification
    failed_count = len(failed_names)
    notifications.notify_execution_result(
        total=len(task_names),
        passed=success_count,
        failed=failed_count,
        context="tasks",
        failed_names=failed_names if failed_names else None,
        config=config,
    )

    return success_count
