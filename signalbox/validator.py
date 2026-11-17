# Configuration validation for signalbox

import os
import re

import yaml

from .config import load_config, get_config_value, load_global_config, resolve_path, config_sources, CONFIG_FILE
from .cron import schedule_error
from .helpers import is_valid_name, yaml_files, NAME_RULE

SEVERITIES = ("info", "warning", "critical")
EXECUTION_MODES = ("serial", "parallel")
LOG_LIMIT_TYPES = ("count", "age", "size")


class ValidationResult:
    """Container for validation results."""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.files_used = []
        self.config = None
        self.global_config = None

    @property
    def is_valid(self):
        """Check if configuration is valid (no errors, or no warnings if strict mode)."""
        strict_mode = get_config_value("validation.strict", False)
        return len(self.errors) == 0 and (not strict_mode or len(self.warnings) == 0)

    @property
    def has_issues(self):
        """Check if there are any errors or warnings."""
        return len(self.errors) > 0 or len(self.warnings) > 0


def _name_error(kind, name):
    return f"{kind} name {name!r} is invalid: {NAME_RULE}"


def _invalid_number(value, minimum=0):
    """True unless value is a real number >= minimum (YAML true/false are not numbers)."""
    return isinstance(value, bool) or not isinstance(value, (int, float)) or value < minimum


def _invalid_whole_number(value, minimum=0):
    """True unless value is a whole number >= minimum."""
    return _invalid_number(value, minimum) or not isinstance(value, int)


# On/off settings: a quoted "false" is non-empty text, which Python treats as on
BOOLEAN_SETTINGS = (
    "include_catalog",
    "alerts.notifications.enabled",
    "alerts.notifications.on_failure_only",
    "group_notifications.enabled",
    "group_notifications.on_failure_only",
    "group_notifications.show_failed_names",
    "execution.capture_stdout",
    "execution.capture_stderr",
    "logging.include_command",
    "logging.include_return_code",
    "tray.enabled",
    "validation.strict",
    "display.colors",
    "display.include_paths",
)


def validate_run_settings():
    """Check the global settings that every run depends on.

    Run before every task and group run as well as by `signalbox validate`, so
    both apply the same rule. Fallbacks match the shipped signalbox.yaml.
    """
    errors = []
    for key, default in (
        ("execution.default_timeout", 300),
        ("execution.min_timeout", 1),
        ("logging.max_file_size_mb", 5),  # 0 = no size limit
        ("alerts.notifications.cooldown_minutes", 60),
        ("alerts.retention.max_days", 30),
    ):
        value = get_config_value(key, default)
        if _invalid_number(value):
            errors.append(f"{key} must be a number >= 0, got {value!r}")
    for key, default, minimum in (
        ("execution.max_parallel_workers", 5, 1),  # 0 would crash every parallel group
        ("alerts.retention.max_entries", 1000, 0),
    ):
        value = get_config_value(key, default)
        if _invalid_whole_number(value, minimum):
            errors.append(f"{key} must be a whole number >= {minimum}, got {value!r}")

    retention = get_config_value("alerts.retention", {})
    per_severity = retention.get("per_severity", {}) if isinstance(retention, dict) else {}
    if not isinstance(retention, dict):
        errors.append(f"alerts.retention must be a mapping, got {retention!r}")
    elif not isinstance(per_severity, dict):
        errors.append(f"alerts.retention.per_severity must be a mapping, got {per_severity!r}")
    else:
        errors.extend(
            f"alerts.retention.per_severity.{severity} must be a number >= 0, got {days!r}"
            for severity, days in per_severity.items()
            if _invalid_number(days)
        )
    return errors


def validate_task_for_run(task):
    """Check only what would stop a task from running correctly.

    Run before every execution. Problems that don't affect running (a missing
    description, a bad alert pattern) are left to `signalbox validate`, so they
    never block a scheduled run.

    Returns:
        list: Error messages (empty if the task can run)
    """
    if not isinstance(task, dict):
        return [f"Task entry must be a mapping, got {type(task).__name__}"]

    errors = []
    label = f"Task '{task.get('name', 'unknown')}'"
    if "name" not in task:
        errors.append("Task missing 'name' field")
    elif not is_valid_name(task["name"]):
        errors.append(_name_error("Task", task["name"]))
    if "command" not in task:
        errors.append(f"{label} missing 'command' field")
    elif not isinstance(task["command"], str):
        errors.append(f"{label} 'command' must be a string")

    if "timeout" in task:
        timeout = task["timeout"]
        if _invalid_number(timeout):
            errors.append(f"{label} has invalid timeout (must be a number >= 0, got {timeout!r})")

    if "cwd" in task and not isinstance(task["cwd"], str):
        errors.append(f"{label} 'cwd' must be a path string")

    # Alerts are checked after the command has run, so a malformed list would
    # fail every run after its side effects, without saving state or rotating logs.
    if "alerts" in task:
        if not isinstance(task["alerts"], list):
            errors.append(f"{label} alerts field must be a list")
        else:
            for idx, alert in enumerate(task["alerts"], start=1):
                if not isinstance(alert, dict):
                    errors.append(f"{label} alert #{idx} must be a dict")

    return errors


def validate_log_limit(log_limit, label):
    """Check a log_limit mapping ({type: count|age|size, value: N})."""
    if not isinstance(log_limit, dict):
        return [f"{label} log_limit must be a mapping with 'type' and 'value'"]
    errors = []
    if log_limit.get("type") not in LOG_LIMIT_TYPES:
        errors.append(
            f"{label} log_limit type must be one of {', '.join(LOG_LIMIT_TYPES)}, got {log_limit.get('type')!r}"
        )
    value = log_limit.get("value")
    if _invalid_number(value, minimum=1):
        errors.append(f"{label} log_limit value must be a number >= 1, got {value!r}")
    return errors


def validate_task(task):
    """Check a single task definition fully (used by `signalbox validate`).

    Returns:
        list: Error messages (empty if the task is valid)
    """
    errors = validate_task_for_run(task)
    if not isinstance(task, dict):
        return errors

    label = f"Task '{task.get('name', 'unknown')}'"
    if "description" not in task:
        errors.append(f"{label} missing 'description' field")
    if "log_limit" in task:
        errors.extend(validate_log_limit(task["log_limit"], label))

    alerts_list = task.get("alerts")
    if isinstance(alerts_list, list):
        for idx, alert in enumerate(alerts_list, start=1):
            if not isinstance(alert, dict):
                continue
            for field in ("pattern", "message"):
                if field not in alert:
                    errors.append(f"{label} alert #{idx} missing '{field}' field")
            if "pattern" in alert:
                try:
                    re.compile(str(alert["pattern"]))  # alerts.py searches for a number as text
                except (re.error, TypeError) as e:
                    errors.append(f"{label} alert #{idx} has invalid regex pattern: {e}")
            if "severity" in alert and alert["severity"] not in SEVERITIES:
                errors.append(f"{label} alert #{idx} has invalid severity (must be info, warning, or critical)")
            # A quoted "false" is a non-empty string, which Python treats as true
            for field in ("notify", "on_failure_only"):
                if alert.get(field) is not None and not isinstance(alert[field], bool):
                    errors.append(f"{label} alert #{idx} '{field}' must be true or false, got {alert[field]!r}")

    return errors


def validate_group(group):
    """Check a single group definition (references to tasks are checked separately).

    Returns:
        list: Error messages (empty if the group is valid)
    """
    if not isinstance(group, dict):
        return [f"Group entry must be a mapping, got {type(group).__name__}"]

    errors = []
    label = f"Group '{group.get('name', 'unknown')}'"
    if "name" not in group:
        errors.append("Group missing 'name' field")
    elif not is_valid_name(group["name"]):
        errors.append(_name_error("Group", group["name"]))
    for field in ("description", "tasks"):
        if field not in group:
            errors.append(f"{label} missing '{field}' field")

    if "tasks" in group:
        if not isinstance(group["tasks"], list):
            errors.append(f"{label} 'tasks' must be a list of task names")
        else:
            for entry in group["tasks"]:
                if not isinstance(entry, str):
                    errors.append(f"{label} has invalid task entry: expected string, got {type(entry).__name__}")

    if "stop_on_error" in group and not isinstance(group["stop_on_error"], bool):
        # A quoted "false" is a non-empty string, which Python treats as true
        errors.append(f"{label} 'stop_on_error' must be true or false, got {group['stop_on_error']!r}")

    if "execution" in group and group["execution"] not in EXECUTION_MODES:
        errors.append(f"{label} has invalid execution mode {group['execution']!r} (must be serial or parallel)")

    if "schedule" in group:
        schedule = group["schedule"]
        if isinstance(schedule, dict):
            if "cron" not in schedule:
                errors.append(f"{label} has schedule dict without 'cron' key")
        elif not isinstance(schedule, str):
            errors.append(f"{label} has invalid schedule type: expected string or dict, got {type(schedule).__name__}")

    return errors


def _validate_file(fpath, kind):
    """Parse one task or group file and validate every entry in it."""
    try:
        with open(fpath, "r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"YAML syntax error: {e}"]
    except Exception as e:
        return [f"Error loading: {e}"]

    if not isinstance(data, dict) or kind not in data:
        return [f"No '{kind}' key found"]
    entries = data[kind]
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        return [f"'{kind}' must be a list"]

    check = validate_task if kind == "tasks" else validate_group
    return [error for entry in entries for error in check(entry)]


def validate_configuration():
    """Validate all configuration files (catalog files only when include_catalog is enabled).

    Returns:
        ValidationResult: Object containing validation results
    """
    result = ValidationResult()

    try:
        task_files_found = False
        tasks_dir = None

        # Per-file checks over the same directories the loader reads, so errors are grouped by file
        for directory, kind, is_catalog in config_sources():
            if kind == "tasks" and not is_catalog:
                tasks_dir = directory
            if not os.path.isdir(directory):
                continue
            for fname in yaml_files(directory):
                fpath = os.path.join(directory, fname)
                task_files_found = task_files_found or kind == "tasks"
                result.files_used.append(fpath)
                file_errors = _validate_file(fpath, kind)
                if file_errors:
                    prefix = "[Catalog] " if is_catalog else ""
                    heading = "Task Config File" if kind == "tasks" else "Group Config File"
                    result.errors.append(f"\n{prefix}{heading}:  {fname}")
                    result.errors.extend(f"{prefix} - {error}" for error in file_errors)

        if not task_files_found:
            result.errors.append(f"No task files found ({tasks_dir})")
            return result

        config_file = resolve_path(CONFIG_FILE)
        if os.path.exists(config_file):
            result.files_used.insert(0, f"{config_file} (global config)")

        # Cross-file checks on the merged configuration
        try:
            result.config = load_config(suppress_warnings=True)
        except Exception as e:
            result.errors.append(f"Error loading config: {e}")
            return result
        if not isinstance(result.config, dict):
            result.errors.append("Error loading config: no configuration returned")
            return result

        _validate_tasks(result)
        _validate_groups(result)
        _validate_global_config(result)

    except Exception as e:
        result.errors.append(f"Error loading config: {e}")

    return result


def _validate_tasks(result):
    """Cross-file task checks: duplicates and tasks not used by any group."""
    config = result.config
    tasks = config.get("tasks")

    if not tasks or not isinstance(tasks, list):
        result.errors.append("No tasks defined in config")
        return

    task_names = [t.get("name", f"<unnamed_{i}>") for i, t in enumerate(tasks) if isinstance(t, dict)]

    duplicates = sorted({n for n in task_names if task_names.count(n) > 1})
    if duplicates:
        result.errors.append("Duplicate task names: {}".format(", ".join(duplicates)))

    if get_config_value("validation.warn_unused_tasks", True) and config.get("groups"):
        used_tasks = set()
        for group in config["groups"]:
            if isinstance(group, dict) and isinstance(group.get("tasks"), list):
                used_tasks.update(t for t in group["tasks"] if isinstance(t, str))
        unused = sorted(set(task_names) - used_tasks)
        if unused:
            result.warnings.append("Unused tasks (not in any group): {}".format(", ".join(unused)))


def _validate_groups(result):
    """Cross-file group checks: duplicates, references to missing tasks, cron field count."""
    config = result.config
    groups = [g for g in config.get("groups", []) if isinstance(g, dict)]
    group_names = [g.get("name", f"<unnamed_{i}>") for i, g in enumerate(groups)]
    task_names = {t.get("name") for t in config.get("tasks", []) if isinstance(t, dict)}
    group_sources = config.get("_group_sources", {})

    duplicates = sorted({n for n in group_names if group_names.count(n) > 1})
    if duplicates:
        result.errors.append("Duplicate group names: {}".format(", ".join(duplicates)))

    for group in groups:
        if "name" not in group:
            continue
        group_name = group["name"]
        source_file = os.path.basename(group_sources.get(group_name, "unknown file"))

        if isinstance(group.get("tasks"), list):
            for task_name in group["tasks"]:
                if isinstance(task_name, str) and task_name not in task_names:
                    result.errors.append(f"Group '{group_name}' references non-existent task '{task_name}'")

        schedule = group.get("schedule")
        if isinstance(schedule, dict):
            schedule = schedule.get("cron")
        # Not text: validate_group already reports the type
        error = schedule_error(schedule) if isinstance(schedule, str) else None
        if error:
            result.errors.append(f"Group '{group_name}' in {source_file} schedule is invalid: {error}")


def _validate_global_config(result):
    """Validate global configuration settings."""
    result.global_config = load_global_config()

    if not result.global_config:
        return

    result.errors.extend(validate_run_settings())

    default_limit = get_config_value("default_log_limit", None)
    if default_limit is not None:
        result.errors.extend(validate_log_limit(default_limit, "Global default"))

    # A tray poll interval of 0 never pauses (fallback matches the shipped signalbox.yaml)
    poll_interval = get_config_value("tray.poll_interval", 30)
    if _invalid_whole_number(poll_interval, minimum=1):
        result.errors.append(f"tray.poll_interval must be a whole number >= 1, got {poll_interval!r}")

    for key in BOOLEAN_SETTINGS:
        value = get_config_value(key)
        if value is not None and not isinstance(value, bool):
            result.errors.append(f"{key} must be true or false, got {value!r}")


def get_validation_summary(result):
    """Get a summary of the configuration.

    Returns:
            dict: Summary statistics about the configuration
    """
    if not result.config:
        return {}

    task_count = len(result.config.get("tasks", []))
    group_count = len(result.config.get("groups", []))
    scheduled_count = len([g for g in result.config.get("groups", []) if "schedule" in g])

    summary = {"tasks": task_count, "groups": group_count, "scheduled_groups": scheduled_count}

    if result.global_config:
        summary["default_timeout"] = get_config_value("execution.default_timeout", 300)
        summary["default_log_limit"] = get_config_value("default_log_limit", {})

    return summary
