# Configuration validation for signalbox

import os
import re

import yaml

from .config import load_config, get_config_value, load_global_config, resolve_path, CONFIG_FILE, CONFIG_SOURCES
from .helpers import is_valid_name

SEVERITIES = ("info", "warning", "critical")
EXECUTION_MODES = ("serial", "parallel")


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
    return (
        f"{kind} name {name!r} is invalid: use only letters, digits, '_', '-' and '.', "
        "and do not start with '.' or '-'"
    )


def validate_task(task):
    """Check a single task definition.

    Used both by `config validate` and before a task is run.

    Returns:
        list: Error messages (empty if the task is valid)
    """
    if not isinstance(task, dict):
        return [f"Task entry must be a mapping, got {type(task).__name__}"]

    errors = []
    label = f"Task '{task.get('name', 'unknown')}'"
    if "name" not in task:
        errors.append("Task missing 'name' field")
    elif not is_valid_name(task["name"]):
        errors.append(_name_error("Task", task["name"]))
    for field in ("command", "description"):
        if field not in task:
            errors.append(f"{label} missing '{field}' field")
    if "command" in task and not isinstance(task["command"], str):
        errors.append(f"{label} 'command' must be a string")

    if "timeout" in task:
        timeout = task["timeout"]
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout < 0:
            errors.append(f"{label} has invalid timeout (must be a number >= 0, got {timeout!r})")

    if "alerts" in task:
        alerts_list = task["alerts"]
        if not isinstance(alerts_list, list):
            errors.append(f"{label} alerts field must be a list")
            alerts_list = []
        for idx, alert in enumerate(alerts_list, start=1):
            if not isinstance(alert, dict):
                errors.append(f"{label} alert #{idx} must be a dict")
                continue
            for field in ("pattern", "message"):
                if field not in alert:
                    errors.append(f"{label} alert #{idx} missing '{field}' field")
            if "pattern" in alert:
                try:
                    re.compile(alert["pattern"])
                except (re.error, TypeError) as e:
                    errors.append(f"{label} alert #{idx} has invalid regex pattern: {e}")
            if "severity" in alert and alert["severity"] not in SEVERITIES:
                errors.append(f"{label} alert #{idx} has invalid severity (must be info, warning, or critical)")

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


def _yaml_files(directory):
    """List YAML files in a directory the same way the config loader does (dotfiles skipped)."""
    return [f for f in sorted(os.listdir(directory)) if not f.startswith(".") and f.endswith((".yaml", ".yml"))]


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
        include_catalog = get_config_value("include_catalog", False)
        task_files_found = False
        tasks_dir = None

        # Per-file checks, so errors are grouped under the file they come from
        for key, kind, fallback, is_catalog in CONFIG_SOURCES:
            if is_catalog and not include_catalog:
                continue
            directory = resolve_path(get_config_value(key, fallback))
            if kind == "tasks" and not is_catalog:
                tasks_dir = directory
            if not os.path.isdir(directory):
                continue
            for fname in _yaml_files(directory):
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
        if isinstance(schedule, str) and not schedule.startswith("@") and len(schedule.split()) != 5:
            result.warnings.append(
                f"Group '{group_name}' in {source_file} schedule may be invalid: '{schedule}' (expected 5 cron fields)"
            )


def _validate_global_config(result):
    """Validate global configuration settings."""
    result.global_config = load_global_config()

    if not result.global_config:
        return

    # Validate timeout value
    timeout = get_config_value("execution.default_timeout", 300)
    if not isinstance(timeout, (int, float)) or timeout < 0:
        result.warnings.append("Invalid timeout value: {} (should be >= 0)".format(timeout))


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
