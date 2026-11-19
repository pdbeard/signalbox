# Task and group execution logic for signalbox
#
# SECURITY NOTE: This module executes shell commands with shell=True to support
# pipes, redirection, and complex bash scripts. Commands are executed with the
# full permissions of the user running signalbox.
#
# Configuration files MUST be trusted. See documentation/SECURITY.md for details.
#
import fcntl
import os
import signal
import subprocess
import time
from datetime import datetime
from string import Template
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import click

from .config import get_config_value, find_config_home, find_entry, resolve_path
from .runtime import save_task_runtime_state, setting_with_tray_override
from .log_manager import ensure_log_dir, get_log_path, get_task_log_dir, write_execution_log, rotate_logs
from .exceptions import (
    TaskNotFoundError,
    ExecutionError,
    ExecutionTimeoutError,
    ValidationError,
    ConfigurationError,
    TaskSkipped,
)
from . import notifications
from . import alerts
from .helpers import (
    format_timestamp,
    load_env_file,
    mask_secrets,
    SECRET_NAME_PATTERN,
    on_this_platform,
    current_platform,
)
from .validator import validate_task_for_run, validate_run_settings

# After the final SIGKILL, how long to wait for the pipes to close before giving up on the output
KILL_GRACE_SECONDS = 5

# The time limit of each run_if check (a check is quick: is a drive mounted, is a host up)
RUN_IF_TIMEOUT = 30
# Exit codes of a shell that could not run the command at all: a typo, not a reason to skip
CANNOT_RUN_CODES = (126, 127)

# Processes started by run_command that are still running, so an interrupted
# parallel group can stop them (Ctrl+C reaches only the main thread).
_running = set()


def _signal_group(proc, sig):
    """Send sig to every process in the task's process group (the shell and anything it started)."""
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        pass


def stop_grace_seconds():
    """How long a task may take to exit after SIGTERM before it gets SIGKILL (0 = SIGKILL at once).

    Fallback matches the value in the shipped signalbox.yaml.
    """
    return get_config_value("execution.stop_grace_seconds", 5)


def _stop_and_collect(proc, grace):
    """Stop the task's process group and return its (stdout, stderr).

    SIGTERM first, so the task can clean up; SIGKILL after `grace` seconds, and
    always at the end for anything left in the group (a child that ignored
    SIGTERM, or one that outlived the shell).
    """
    output = None
    if grace > 0:
        _signal_group(proc, signal.SIGTERM)
        try:
            output = proc.communicate(timeout=grace)  # keeps reading, so a busy task cannot block on a full pipe
        except subprocess.TimeoutExpired:
            pass
    _signal_group(proc, signal.SIGKILL)
    if output is not None:
        return output
    try:
        # Retrying communicate() keeps the output read so far
        return proc.communicate(timeout=KILL_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        # Something escaped the process group (e.g. daemonized) and still holds the pipes
        proc.stdout.close()
        proc.stderr.close()
        proc.wait()
        return "", ""


def stop_all_running(grace):
    """Stop every running task, as _stop_and_collect does, from another thread (an interrupted parallel group).

    The threads that started the tasks still collect their output and record the runs.
    """
    procs = list(_running)
    if grace > 0:
        for proc in procs:
            _signal_group(proc, signal.SIGTERM)
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline and any(proc.poll() is None for proc in procs):
            time.sleep(0.05)
    for proc in procs:
        _signal_group(proc, signal.SIGKILL)


def run_command(command, timeout=None, cwd=None, env=None, grace=None):
    """Run a shell command the way signalbox runs every task.

    - The command gets its own session/process group, so a timeout (or Ctrl+C)
      stops everything it started, not just the shell: SIGTERM first, then
      SIGKILL after `grace` seconds (execution.stop_grace_seconds by default).
    - stdin is /dev/null: a command that prompts fails fast instead of hanging
      invisibly (its output is captured) until the timeout.
    - cwd is explicit, so manual and scheduled runs behave the same.
    - env, if given, is the complete environment of the command.

    Returns:
        subprocess.CompletedProcess with text stdout/stderr

    Raises:
        subprocess.TimeoutExpired: With whatever output was captured, and the
            exit status of the stopped shell as its `returncode` attribute
    """
    if grace is None:
        grace = stop_grace_seconds()
    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        # Output that is not valid in the locale's encoding (binary data, a
        # latin-1 file) is replaced with U+FFFD instead of failing the run.
        errors="replace",
        start_new_session=True,
    )
    _running.add(proc)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        stdout, stderr = _stop_and_collect(proc, grace)
        timed_out = subprocess.TimeoutExpired(command, timeout, output=stdout, stderr=stderr)
        timed_out.returncode = proc.returncode  # -15 if SIGTERM stopped it, -9 if it needed SIGKILL
        raise timed_out
    except BaseException:
        # The task is in its own session, so Ctrl+C no longer reaches it directly
        try:
            _stop_and_collect(proc, grace)
        finally:
            _signal_group(proc, signal.SIGKILL)  # a second Ctrl+C during the grace period still stops it
            proc.wait()
        raise
    finally:
        _running.discard(proc)
    return subprocess.CompletedProcess(command, proc.returncode, stdout, stderr)


def resolve_task_cwd(task):
    """Working directory for a task: its 'cwd' (relative to the signalbox home), or the home itself."""
    cwd = task.get("cwd")
    return resolve_path(cwd) if cwd else find_config_home()


def prepare_run(task):
    """What exactly runs for a task: {'command', 'cwd', 'env', 'secrets'}.

    The one place that turns a task entry into a run, so a run and any preview of it agree.
    The environment is signalbox's own, then the env_file, then 'env' (whose values can use
    $VAR from the two before). 'secrets' are the values to mask in logs: the variables listed
    in 'mask', and the task's own variables (env_file or env) whose names look secret.

    Raises:
        ConfigurationError: if the working directory or the env_file does not exist,
            or the env_file has a line that is not KEY=VALUE
    """
    cwd = resolve_task_cwd(task)
    if not os.path.isdir(cwd):
        raise ConfigurationError(f"Working directory for task '{task.get('name')}' does not exist: {cwd}")
    env = dict(os.environ)
    own = []  # the variables this task sets
    if task.get("env_file"):
        from_file = load_env_file(resolve_path(task["env_file"]))
        env.update(from_file)
        own.extend(from_file)
    for key, value in (task.get("env") or {}).items():
        env[key] = Template(str(value)).safe_substitute(env)
        own.append(key)
    to_mask = set(task.get("mask") or []) | {key for key in own if SECRET_NAME_PATTERN.search(key)}
    secrets = [env[key] for key in to_mask if key in env]
    return {"command": task["command"], "cwd": cwd, "env": env, "secrets": secrets}


def find_task(name, config):
    """Find a task in the config by name.

    Raises:
        TaskNotFoundError: If no task with the given name exists in config.
    """
    task = find_entry(config, "tasks", name)
    if not task:
        raise TaskNotFoundError(name)
    return task


def last_log_name(name, config):
    """File name of the log this process wrote for the task's latest run ('' if it did not run).

    Recorded per run rather than looked up as the newest file, which could be
    another process's run of the same task.
    """
    task = find_entry(config, "tasks", name) or {}
    return os.path.basename(task.get("last_log", ""))


def task_timeout(task, warn=False):
    """The task's time limit in seconds, or None for no limit.

    Its own 'timeout', else execution.default_timeout; 0 means no limit, and a
    smaller non-zero value is raised to execution.min_timeout.
    """
    timeout = task.get("timeout", get_config_value("execution.default_timeout", 300))
    # Security: Enforce minimum timeout to prevent DOS via infinite hangs
    min_timeout = get_config_value("execution.min_timeout", 1)
    if timeout == 0:
        return None
    if timeout < min_timeout:
        if warn:
            click.echo(
                f"Warning: Timeout {timeout}s is less than the minimum {min_timeout}s. Signalbox uses the minimum.",
                err=True,
            )
        return min_timeout
    return timeout


@contextmanager
def _run_lock(name, overlap, wait_limit):
    """Yield True if this run may start, False if it must skip (overlap: skip | wait | allow).

    The lock is a flock on logs/<task>/.run.lock, held for the whole run. The
    system releases it when the process ends, so a crash cannot leave a stale
    lock. Each open() has its own lock, so it also works between the threads of
    a parallel group.
    """
    if overlap == "allow":
        yield True
        return
    lock_dir = get_task_log_dir(name)
    os.makedirs(lock_dir, exist_ok=True)
    with open(os.path.join(lock_dir, ".run.lock"), "w") as lock:
        deadline = None if wait_limit is None else time.monotonic() + wait_limit
        while True:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if overlap == "skip" or (deadline is not None and time.monotonic() >= deadline):
                    yield False
                    return
                time.sleep(0.2)
        yield True


def _run_if_failure(task, run):
    """The reason to skip the task, or None if every run_if check exits 0.

    Raises:
        ConfigurationError: if a check cannot run at all (exit 126/127: not found or not executable)
    """
    checks = task.get("run_if") or []
    for check in [checks] if isinstance(checks, str) else checks:
        try:
            result = run_command(check, timeout=RUN_IF_TIMEOUT, cwd=run["cwd"], env=run["env"])
        except subprocess.TimeoutExpired:
            return f"run_if timed out after {RUN_IF_TIMEOUT}s: {check}"
        if result.returncode in CANNOT_RUN_CODES:
            raise ConfigurationError(f"run_if check cannot run (exit {result.returncode}): {check}")
        if result.returncode != 0:
            return f"run_if failed: {check}"
    return None


def _skip(name, task, config, reason, record=True):
    """Report and record a skipped run, then raise TaskSkipped.

    A skip writes no log file: a task skipped every minute would push its real
    logs out of rotation. It is recorded in the runtime state instead.
    """
    click.echo(f"Task {name} skipped: {reason}")
    if record:
        timestamp = format_timestamp(datetime.now())
        source = config["_task_sources"].get(name)
        if source:
            save_task_runtime_state(name, source, timestamp, "skipped", skip_reason=reason)
        task["last_status"] = "skipped"
        task["last_run"] = timestamp
    task["last_log"] = ""
    raise TaskSkipped(name, reason)


def _execute(task, name, config, run):
    """Run the task subprocess and return (result, log_file, timestamp).

    Handles timeout resolution and log path preparation. A task may override
    the global execution.default_timeout with its own 'timeout' field
    (in seconds, 0 = no timeout).

    Raises:
        ExecutionTimeoutError: If the subprocess exceeds the configured timeout.
    """
    timeout = task_timeout(task, warn=True)
    ensure_log_dir(name)
    timestamp = format_timestamp(datetime.now())
    log_file = get_log_path(name, timestamp)

    try:
        result = run_command(run["command"], timeout=timeout, cwd=run["cwd"], env=run["env"])
    except subprocess.TimeoutExpired as e:
        # Log, check alerts on the partial output and record the failure like
        # any other run. The return code is how the stop ended it: -15 (SIGTERM) or -9 (SIGKILL).
        stderr = _as_text(e.stderr) + f"\n[TIMED OUT after {e.timeout}s]"
        returncode = getattr(e, "returncode", None)
        timed_out = subprocess.CompletedProcess(
            run["command"], -9 if returncode is None else returncode, _as_text(e.stdout), stderr
        )
        _post_execution(name, task, timed_out, log_file, timestamp, config, run)
        raise ExecutionTimeoutError(name, timeout)

    return result, log_file, timestamp


def _as_text(output):
    """Normalize partial output from TimeoutExpired, which may be bytes, str, or None."""
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode(errors="replace")
    return output


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
        notify = setting_with_tray_override("alerts.notifications.enabled", True)
    if not notify:
        return False

    on_failure_only = alert.get("on_failure_only")
    if on_failure_only is None:
        on_failure_only = get_config_value("alerts.notifications.on_failure_only", True)
    if on_failure_only and alert.get("severity", "info") == "info":
        return False

    cooldown = get_config_value("alerts.notifications.cooldown_minutes", 60)
    return not (cooldown and alerts.notified_within(name, alert["pattern"], cooldown))


def _post_execution(name, task, result, log_file, timestamp, config, run):
    """Handle all post-execution concerns: logging, alerts, notifications, log rotation, runtime state."""
    # Secrets are masked in what is written; alerts below still match the real output
    secrets = run["secrets"]
    write_execution_log(
        log_file,
        mask_secrets(run["command"], secrets),
        result.returncode,
        mask_secrets(result.stdout, secrets),
        mask_secrets(result.stderr, secrets),
    )

    # Check for alert patterns in output
    combined_output = result.stdout + "\n" + result.stderr
    triggered_alerts = alerts.check_alert_patterns(name, task, combined_output)

    # Save and optionally notify for each triggered alert
    for alert in triggered_alerts:
        alert["notified"] = _should_notify(name, alert)
        alerts.save_alert(name, alert)
        # str(): a number here is reported by `signalbox validate`; it must not fail the run after the command
        click.echo(f"  [{str(alert['severity']).upper()}] {alert['message']}")
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
        # Fallback matches the value in the shipped signalbox.yaml.
        per_severity=retention.get("per_severity", {"critical": 90, "warning": 30, "info": 7}),
    )

    status = "success" if result.returncode == 0 else "failed"
    click.echo(f"Task {name} {status}. Log: {log_file}")

    task_source_file = config["_task_sources"].get(name)
    if task_source_file:
        save_task_runtime_state(name, task_source_file, timestamp, status)

    task["last_status"] = status
    task["last_run"] = timestamp
    task["last_log"] = log_file


def run_task(name, config):
    """Execute a single task and log the results.

    Args:
        name: Name of the task to run
        config: Full configuration dict containing tasks

    Returns:
        bool: True if task executed successfully (exit code 0), False otherwise

    Raises:
        TaskSkipped: If the task did not run on purpose: not for this platform,
            already running (overlap), or a run_if check failed
        TaskNotFoundError: If task not found in configuration
        ValidationError: If the task can't be run (e.g. missing 'command')
        ConfigurationError: If the task's working directory or env_file does not exist
        ExecutionTimeoutError: If task execution times out
        ExecutionError: If task execution fails for any other reason
    """
    task = find_task(name, config)
    errors = validate_task_for_run(task) + validate_run_settings()
    if errors:
        raise ValidationError("; ".join(errors))
    if not on_this_platform(task):
        # Not recorded: on this machine the task does not exist (it is hidden from the tray and status)
        _skip(name, task, config, f"not for this platform ({current_platform()})", record=False)
    run = prepare_run(task)
    with _run_lock(name, task.get("overlap", "skip"), task_timeout(task)) as may_run:
        if not may_run:
            _skip(name, task, config, "already running")
        reason = _run_if_failure(task, run)
        if reason:
            _skip(name, task, config, reason)
        try:
            result, log_file, timestamp = _execute(task, name, config, run)
            _post_execution(name, task, result, log_file, timestamp, config, run)
            return result.returncode == 0
        except (ExecutionTimeoutError, TaskNotFoundError):
            raise
        except Exception as e:
            raise ExecutionError(name, str(e))


def _run_group_task(task_name, config):
    """Run one task of a group, converting exceptions into a failed (or skipped) result."""
    click.echo("")  # Add a blank line before each group task execution output
    click.echo(f"Running {task_name}...")
    result = {"name": task_name, "status": "success", "error": ""}
    try:
        if not run_task(task_name, config):
            result["status"] = "failed"
    except TaskSkipped as e:
        # Skipped on purpose (run_if, overlap, platform): it does not count against the group
        result.update(status="skipped", error=e.reason, skip="condition")
    except Exception as e:
        result.update(status="failed", error=e.message if hasattr(e, "message") else str(e))
        click.echo(f"Error: {result['error']}")
    result["log_file"] = last_log_name(task_name, config)
    return result


def _notify_group_result(results):
    """Send the group summary notification for a list of task results."""
    ran = [r for r in results if r["status"] != "skipped"]
    if not ran:
        return  # nothing ran: there is no result to report
    failed_names = [r["name"] for r in ran if r["status"] != "success"]
    passed = len(ran) - len(failed_names)
    notifications.notify_execution_result(
        total=len(ran),
        passed=passed,
        failed=len(failed_names),
        context="tasks",
        failed_names=failed_names or None,
    )


def run_group_parallel(task_names, config):
    """Execute multiple tasks in parallel.

    Args:
            task_names: List of task names to execute
            config: Full configuration dict

    Returns:
            list: One dict per task, in task_names order, with keys 'name',
                  'status' ('success', 'failed' or 'skipped'), 'error' and 'log_file'
                  (and 'skip': 'condition' for a skipped task)
    """
    max_workers = get_config_value("execution.max_parallel_workers", 5)

    executor = ThreadPoolExecutor(max_workers=max_workers)
    futures = [executor.submit(_run_group_task, name, config) for name in task_names]
    try:
        results = [future.result() for future in futures]
    except KeyboardInterrupt:
        # Tasks run in their own sessions, so Ctrl+C never reaches them: stop
        # queued tasks from starting, then stop the ones already running.
        executor.shutdown(wait=False, cancel_futures=True)
        stop_all_running(stop_grace_seconds())
        raise
    executor.shutdown()

    # Print summary
    click.echo("\nParallel execution summary:")
    success_count = sum(1 for r in results if r["status"] == "success")
    click.echo(f"  Completed: {len(results)}/{len(task_names)}")
    click.echo(f"  Successful: {success_count}/{len(results)}")
    for label, status in (("Failed", "failed"), ("Skipped", "skipped")):
        names = [r["name"] for r in results if r["status"] == status]
        if names:
            click.echo(f"  {label}: {', '.join(names)}")

    _notify_group_result(results)
    return results


def run_group_serial(task_names, config, stop_on_error):
    """Execute multiple tasks sequentially.

    Args:
            task_names: List of task names to execute
            config: Full configuration dict
            stop_on_error: If True, stop execution when a task fails

    Returns:
            list: One dict per task, in task_names order, with keys 'name',
                  'status' ('success', 'failed' or 'skipped'), 'error' and 'log_file'.
                  'skip' tells why a task was skipped: 'condition' (run_if, overlap,
                  platform; neutral) or 'stop_on_error' (an earlier task failed)
    """
    results = []
    stopped = False
    for task_name in task_names:
        if stopped:
            results.append(
                {"name": task_name, "status": "skipped", "error": "", "log_file": "", "skip": "stop_on_error"}
            )
            continue
        result = _run_group_task(task_name, config)
        results.append(result)
        # A skipped task is not a failure, so it does not stop the group
        if result["status"] == "failed" and stop_on_error:
            stopped = True
            click.echo(f"Task {task_name} failed. The remaining tasks do not run (stop_on_error: true)")

    _notify_group_result(results)
    return results
