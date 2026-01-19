# Script and group execution logic for signalbox
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
from .runtime import save_script_runtime_state
from .log_manager import ensure_log_dir, get_log_path, write_execution_log, rotate_logs
from .exceptions import ScriptNotFoundError, ExecutionError, ExecutionTimeoutError
from . import notifications
from . import alerts
from .helpers import format_timestamp


def run_script(name, config):
    """Execute a single script and log the results.

    Args:
            name: Name of the script to run
            config: Full configuration dict containing scripts

    Returns:
            bool: True if script executed successfully (exit code 0), False otherwise

    Raises:
            ScriptNotFoundError: If script not found in configuration
            ExecutionTimeoutError: If script execution times out
            ExecutionError: If script execution fails for any other reason
    """
    script = next((s for s in config["scripts"] if s["name"] == name), None)
    if not script:
        raise ScriptNotFoundError(name)

    # Prepare logging
    ensure_log_dir(name)
    timestamp = format_timestamp(datetime.now())
    log_file = get_log_path(name, timestamp)

    # Get timeout setting
    timeout = get_config_value("execution.default_timeout", 300)
    # Security: Enforce minimum timeout of 1 second to prevent DOS attacks
    # A timeout of 0 would mean "no timeout" which could hang forever
    min_timeout = get_config_value("execution.min_timeout", 1)
    if timeout == 0:
        timeout = None
    elif timeout < min_timeout:
        click.echo(f"Warning: Timeout {timeout}s is below minimum {min_timeout}s, using minimum", err=True)
        timeout = min_timeout

    try:
        # Execute the script
        result = subprocess.run(script["command"], shell=True, capture_output=True, text=True, timeout=timeout)

        # Write log file
        write_execution_log(log_file, script["command"], result.returncode, result.stdout, result.stderr)

        # Check for alert patterns in output
        combined_output = result.stdout + "\n" + result.stderr
        triggered_alerts = alerts.check_alert_patterns(name, script, combined_output)
        
        # Save and optionally notify for each triggered alert
        if triggered_alerts:
            alerts_enabled = get_config_value("alerts.notifications.enabled", True)
            for alert in triggered_alerts:
                alerts.save_alert(name, alert)
                
                # Send notification if alerts are enabled
                if alerts_enabled:
                    notifications.send_notification(
                        title=f"Alert: {name}",
                        message=alert["message"],
                        urgency="critical" if alert["severity"] == "critical" else "normal"
                    )
                    
                # Log to console
                severity_label = alert["severity"].upper()
                click.echo(f"  [{severity_label}] {alert['message']}")

        # Rotate old logs
        rotate_logs(script)

        # Determine status and save runtime state
        status = "success" if result.returncode == 0 else "failed"
        click.echo(f"Script {name} {status}. Log: {log_file}")

        script_source_file = config["_script_sources"].get(name)
        if script_source_file:
            save_script_runtime_state(name, script_source_file, timestamp, status)

        # Update in-memory config
        script["last_status"] = status
        script["last_run"] = timestamp

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        raise ExecutionTimeoutError(name, timeout)
    except Exception as e:
        raise ExecutionError(name, str(e))


def run_group_parallel(script_names, config):
    """Execute multiple scripts in parallel.

    Args:
            script_names: List of script names to execute
            config: Full configuration dict

    Returns:
            int: Number of scripts that executed successfully
    """
    max_workers = get_config_value("execution.max_parallel_workers", 5)

    def run_script_wrapper(script_name):
        """Wrapper for parallel execution that catches exceptions."""
        try:
            click.echo(f"Running {script_name}...")
            success = run_script(script_name, config)
            return (script_name, success, None)
        except Exception as e:
            click.echo(f"Error: {e.message if hasattr(e, 'message') else str(e)}")
            return (script_name, False, str(e))

    # Execute scripts in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_script_wrapper, name): name for name in script_names}
        results = []
        for future in as_completed(futures):
            script_name, success, error = future.result()
            results.append((script_name, success, error))

    # Print summary
    click.echo("\nParallel execution summary:")
    success_count = sum(1 for _, success, _ in results if success)
    click.echo(f"  Completed: {len(results)}/{len(script_names)}")
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
        context="scripts",
        failed_names=failed_names,
        config=config
    )

    return success_count


def run_group_serial(script_names, config, stop_on_error):
    """Execute multiple scripts sequentially.

    Args:
            script_names: List of script names to execute
            config: Full configuration dict
            stop_on_error: If True, stop execution when a script fails

    Returns:
            int: Number of scripts that executed successfully
    """
    success_count = 0
    failed_names = []

    for script_name in script_names:
        try:
            click.echo(f"Running {script_name}...")
            success = run_script(script_name, config)

            if success:
                success_count += 1
            else:
                failed_names.append(script_name)
                if stop_on_error:
                    click.echo(f"⚠️  Script {script_name} failed. Stopping group execution (stop_on_error=true)")
                    break
        except Exception as e:
            click.echo(f"Error: {e.message if hasattr(e, 'message') else str(e)}")
            failed_names.append(script_name)
            if stop_on_error:
                click.echo(f"⚠️  Stopping group execution (stop_on_error=true)")
                break

    # Send notification
    failed_count = len(failed_names)
    notifications.notify_execution_result(
        total=len(script_names),
        passed=success_count,
        failed=failed_count,
        context="scripts",
        failed_names=failed_names if failed_names else None,
        config=config
    )

    return success_count
