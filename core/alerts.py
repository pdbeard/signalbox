# Alert management for signalbox
import os
import re
import json
from datetime import datetime, timedelta
from .config import get_config_value
from .helpers import format_timestamp, parse_timestamp


def get_alerts_dir(task_name):
    """Get the alerts directory for a task."""
    log_dir = get_config_value("paths.log_dir", "logs")
    # Expand ~ to home directory
    if log_dir.startswith("~"):
        log_dir = os.path.expanduser(log_dir)
    # If not absolute, make it relative to config directory
    if not os.path.isabs(log_dir):
        config_dir = os.path.expanduser("~/.config/signalbox")
        log_dir = os.path.join(config_dir, log_dir)

    return os.path.join(log_dir, task_name, "alerts")


def ensure_alerts_dir(task_name):
    """Ensure the alerts directory exists for a task."""
    alerts_dir = get_alerts_dir(task_name)
    os.makedirs(alerts_dir, exist_ok=True)
    return alerts_dir


def check_alert_patterns(task_name, task_config, output):
    """Check task output against alert patterns and record any matches.

    Args:
        task_name: Name of the task
        task_config: Task configuration dict
        output: The stdout/stderr output to check

    Returns:
        list: List of triggered alerts (dicts with pattern, message, severity)
    """
    alerts = task_config.get("alerts", [])
    if not alerts:
        return []

    triggered = []
    for alert in alerts:
        pattern = alert.get("pattern")
        if not pattern:
            continue

        # Check if pattern matches
        if re.search(pattern, output):
            triggered.append(
                {
                    "pattern": pattern,
                    "message": alert.get("message", pattern),
                    "severity": alert.get("severity", "info"),
                    "title": alert.get("title"),
                    "notify": alert.get("notify"),  # Per-alert override for notification
                    "on_failure_only": alert.get("on_failure_only"),  # Per-alert override
                    "timestamp": format_timestamp(datetime.now()),
                    "task_name": task_name,
                }
            )

    return triggered


def save_alert(task_name, alert_data):
    """Save an alert record to the alerts log.

    Args:
        task_name: Name of the task that triggered the alert
        alert_data: Dict with alert information (message, severity, timestamp, etc.)
    """
    alerts_dir = ensure_alerts_dir(task_name)
    alert_log = os.path.join(alerts_dir, "alerts.jsonl")

    # Append alert as JSON line
    with open(alert_log, "a") as f:
        f.write(json.dumps(alert_data) + "\n")


def load_alerts(task_name=None, severity=None, max_days=None):
    """Load alerts from storage, optionally filtered.

    Args:
        task_name: If specified, only load alerts for this task
        severity: If specified, only load alerts with this severity
        max_days: If specified, only load alerts from last N days

    Returns:
        list: List of alert dicts, sorted by timestamp (newest first)
    """
    alerts = []

    # Determine which task directories to check
    log_dir = get_config_value("paths.log_dir", "logs")
    if log_dir.startswith("~"):
        log_dir = os.path.expanduser(log_dir)
    if not os.path.isabs(log_dir):
        config_dir = os.path.expanduser("~/.config/signalbox")
        log_dir = os.path.join(config_dir, log_dir)

    if task_name:
        task_dirs = [task_name]
    else:
        # Get all task directories
        if not os.path.exists(log_dir):
            return []
        task_dirs = [d for d in os.listdir(log_dir) if os.path.isdir(os.path.join(log_dir, d))]

    # Load alerts from each task
    for tname in task_dirs:
        alert_log = os.path.join(log_dir, tname, "alerts", "alerts.jsonl")
        if not os.path.exists(alert_log):
            continue

        with open(alert_log, "r") as f:
            for line in f:
                try:
                    alert = json.loads(line.strip())

                    # Apply severity filter
                    if severity and alert.get("severity") != severity:
                        continue

                    # Apply time filter
                    if max_days:
                        try:
                            alert_time = parse_timestamp(alert.get("timestamp", ""))
                            cutoff = datetime.now() - timedelta(days=max_days)
                            if alert_time < cutoff:
                                continue
                        except Exception:
                            continue

                    alerts.append(alert)
                except json.JSONDecodeError:
                    continue

    # Sort by timestamp (newest first)
    alerts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return alerts


def prune_alerts(task_name, max_days=None, max_entries=None, per_severity=None):
    """Remove old alerts based on retention policy.

    Args:
        task_name: Task to prune alerts for
        max_days: Keep alerts from last N days
        max_entries: Keep at most N alerts
        per_severity: Dict of severity -> max_days overrides
    """
    alerts_dir = get_alerts_dir(task_name)
    alert_log = os.path.join(alerts_dir, "alerts.jsonl")

    if not os.path.exists(alert_log):
        return

    # Load all alerts
    alerts = []
    with open(alert_log, "r") as f:
        for line in f:
            try:
                alerts.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue

    # Apply retention policies
    kept_alerts = []
    cutoff_time = datetime.now() - timedelta(days=max_days) if max_days else None

    for alert in alerts:
        # Check per-severity retention
        severity = alert.get("severity", "info")
        severity_days = per_severity.get(severity) if per_severity else None

        if severity_days:
            severity_cutoff = datetime.now() - timedelta(days=severity_days)
            try:
                alert_time = parse_timestamp(alert.get("timestamp", ""))
                if alert_time < severity_cutoff:
                    continue
            except Exception:
                pass
        elif cutoff_time:
            try:
                alert_time = parse_timestamp(alert.get("timestamp", ""))
                if alert_time < cutoff_time:
                    continue
            except Exception:
                pass

        kept_alerts.append(alert)

    # Apply max_entries limit
    if max_entries and len(kept_alerts) > max_entries:
        # Sort by timestamp and keep most recent
        kept_alerts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        kept_alerts = kept_alerts[:max_entries]

    # Rewrite alert log with kept alerts
    with open(alert_log, "w") as f:
        for alert in kept_alerts:
            f.write(json.dumps(alert) + "\n")


def get_alert_summary():
    """Get a summary of all alerts across all tasks.

    Returns:
        dict: Summary with total count, counts by severity, etc.
    """
    alerts = load_alerts()

    summary = {"total": len(alerts), "by_severity": {}, "by_task": {}}

    for alert in alerts:
        severity = alert.get("severity", "info")
        task = alert.get("task_name", "unknown")

        summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
        summary["by_task"][task] = summary["by_task"].get(task, 0) + 1

    return summary
