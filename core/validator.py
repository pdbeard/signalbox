# Configuration validation for signalbox

import os
import yaml
from .config import load_config, get_config_value, load_global_config, resolve_path


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


def validate_configuration(include_catalog=True):
    """Validate all configuration files, including catalog configs if enabled.

    Args:
        include_catalog (bool): Whether to validate catalog configs as well.
    Returns:
        ValidationResult: Object containing validation results
    """
    result = ValidationResult()

    try:
        # Check if files exist - need to resolve paths relative to config home
        tasks_file = get_config_value("paths.tasks_file", "config/tasks")
        groups_file = get_config_value("paths.groups_file", "config/groups")
        catalog_tasks_file = get_config_value("paths.catalog_tasks_file", "config/catalog/tasks")
        catalog_groups_file = get_config_value("paths.catalog_groups_file", "config/catalog/groups")

        # Resolve all paths to absolute paths
        tasks_file = resolve_path(tasks_file)
        groups_file = resolve_path(groups_file)
        catalog_tasks_file = resolve_path(catalog_tasks_file)
        catalog_groups_file = resolve_path(catalog_groups_file)

        # Strictly validate all user task YAML files for syntax and required fields (user and catalog)
        for task_dir in [tasks_file, catalog_tasks_file]:
            is_catalog = task_dir == catalog_tasks_file
            if os.path.isdir(task_dir):
                for fname in os.listdir(task_dir):
                    if fname.endswith(".yaml") or fname.endswith(".yml"):
                        fpath = os.path.join(task_dir, fname)
                        file_errors = []
                        try:
                            with open(fpath, "r") as f:
                                data = yaml.safe_load(f)
                            if not data or "tasks" not in data:
                                file_errors.append("No 'tasks' key found")
                            else:
                                for task in data["tasks"]:
                                    if "name" not in task:
                                        file_errors.append("Task missing 'name' field")
                                    if "command" not in task:
                                        file_errors.append(
                                            f"Task '{task.get('name', 'unknown')}' missing 'command' field"
                                        )
                                    if "description" not in task:
                                        file_errors.append(
                                            f"Task '{task.get('name', 'unknown')}' missing 'description' field"
                                        )
                                    # Validate alerts field if present
                                    if "alerts" in task:
                                        alerts_list = task["alerts"]
                                        if not isinstance(alerts_list, list):
                                            file_errors.append(
                                                f"Task '{task.get('name', 'unknown')}' alerts field must be a list"
                                            )
                                        else:
                                            for idx, alert in enumerate(alerts_list):
                                                if not isinstance(alert, dict):
                                                    file_errors.append(
                                                        f"Task '{task.get('name', 'unknown')}' alert #{idx+1} must be a dict"
                                                    )
                                                    continue
                                                if "pattern" not in alert:
                                                    file_errors.append(
                                                        f"Task '{task.get('name', 'unknown')}' alert #{idx+1} missing 'pattern' field"
                                                    )
                                                if "message" not in alert:
                                                    file_errors.append(
                                                        f"Task '{task.get('name', 'unknown')}' alert #{idx+1} missing 'message' field"
                                                    )
                                                # Validate severity if present
                                                if "severity" in alert and alert["severity"] not in [
                                                    "info",
                                                    "warning",
                                                    "critical",
                                                ]:
                                                    file_errors.append(
                                                        f"Task '{task.get('name', 'unknown')}' alert #{idx+1} has invalid severity (must be info, warning, or critical)"
                                                    )

                        except yaml.YAMLError as e:
                            file_errors.append(f"YAML syntax error: {e}")
                        except Exception as e:
                            file_errors.append(f"Error loading: {e}")
                        if file_errors:
                            prefix = "[Catalog] " if is_catalog else ""
                            result.errors.append(f"\n{prefix}Task Config File:  {fname}")
                            for err in file_errors:
                                result.errors.append(f"{prefix} - {err}")

        # Strictly validate all user group YAML files for syntax and required fields (user and catalog)
        for group_dir in [groups_file, catalog_groups_file]:
            is_catalog = group_dir == catalog_groups_file
            if os.path.isdir(group_dir):
                for fname in os.listdir(group_dir):
                    if fname.endswith(".yaml") or fname.endswith(".yml"):
                        fpath = os.path.join(group_dir, fname)
                        file_errors = []
                        try:
                            with open(fpath, "r") as f:
                                data = yaml.safe_load(f)
                            if not data or "groups" not in data:
                                file_errors.append("No 'groups' key found")
                            else:
                                for group in data["groups"]:
                                    if "name" not in group:
                                        file_errors.append("Group missing 'name' field")
                                    if "description" not in group:
                                        file_errors.append(
                                            f"Group '{group.get('name', 'unknown')}' missing 'description' field"
                                        )
                                    if "tasks" not in group:
                                        file_errors.append(
                                            f"Group '{group.get('name', 'unknown')}' missing 'tasks' field"
                                        )
                        except yaml.YAMLError as e:
                            file_errors.append(f"YAML syntax error: {e}")
                        except Exception as e:
                            file_errors.append(f"Error loading: {e}")
                        if file_errors:
                            prefix = "[Catalog] " if is_catalog else ""
                            result.errors.append(f"\n{prefix}Group Config File:  {fname}")
                            for err in file_errors:
                                result.errors.append(f"{prefix} - {err}")
        # Validate user tasks/groups, fallback to catalog if enabled
        user_tasks_exists = (
            os.path.isdir(tasks_file) and any(f.endswith((".yaml", ".yml")) for f in os.listdir(tasks_file))
            if os.path.exists(tasks_file)
            else False
        )
        catalog_tasks_exists = (
            os.path.isdir(catalog_tasks_file)
            and any(f.endswith((".yaml", ".yml")) for f in os.listdir(catalog_tasks_file))
            if os.path.exists(catalog_tasks_file)
            else False
        )
        catalog_groups_exists = (
            os.path.isdir(catalog_groups_file)
            and any(f.endswith((".yaml", ".yml")) for f in os.listdir(catalog_groups_file))
            if os.path.exists(catalog_groups_file)
            else False
        )

        if not user_tasks_exists and include_catalog and catalog_tasks_exists:
            # Use catalog tasks as config source
            result.config = {"tasks": [], "groups": []}
            # Load all catalog tasks
            for fname in os.listdir(catalog_tasks_file):
                if fname.endswith(".yaml") or fname.endswith(".yml"):
                    fpath = os.path.join(catalog_tasks_file, fname)
                    try:
                        with open(fpath, "r") as f:
                            catalog_data = yaml.safe_load(f) or {}
                        if "tasks" in catalog_data:
                            result.config["tasks"].extend(catalog_data["tasks"])
                        result.files_used.append(fpath)
                    except Exception as e:
                        result.errors.append(f"[Catalog] Error loading {fpath}: {e}")
            # Load all catalog groups
            if catalog_groups_exists:
                for fname in os.listdir(catalog_groups_file):
                    if fname.endswith(".yaml") or fname.endswith(".yml"):
                        fpath = os.path.join(catalog_groups_file, fname)
                        try:
                            with open(fpath, "r") as f:
                                catalog_data = yaml.safe_load(f) or {}
                            if "groups" in catalog_data:
                                if "groups" not in result.config:
                                    result.config["groups"] = []
                                result.config["groups"].extend(catalog_data["groups"])
                            result.files_used.append(fpath)
                        except Exception as e:
                            result.errors.append(f"[Catalog] Error loading {fpath}: {e}")
            # Validate as normal
            _validate_tasks(result)
            _validate_groups(result)
            _validate_global_config(result)
        elif not user_tasks_exists:
            result.errors.append(f"No tasks file found ({tasks_file})")
            return result
        else:
            try:
                result.config = load_config()
            except Exception as e:
                result.errors.append(f"Error loading config: {e}")
                import traceback
                result.errors.append(f"Traceback: {traceback.format_exc()}")
                return result
            # Track which files are being used
            config_file = resolve_path("config/signalbox.yaml")
            if os.path.exists(config_file):
                result.files_used.append(f"{config_file} (global config)")
            if os.path.exists(tasks_file):
                result.files_used.append(tasks_file)
            if os.path.exists(groups_file):
                result.files_used.append(groups_file)
            # Validate tasks
            _validate_tasks(result)
            # Validate groups
            _validate_groups(result)
            # Validate global config
            _validate_global_config(result)

        # Optionally validate catalog tasks/groups (for extra checking, not as primary source)
        if include_catalog and user_tasks_exists:
            # Validate catalog tasks
            if catalog_tasks_exists:
                for fname in os.listdir(catalog_tasks_file):
                    if fname.endswith(".yaml") or fname.endswith(".yml"):
                        fpath = os.path.join(catalog_tasks_file, fname)
                        try:
                            with open(fpath, "r") as f:
                                catalog_data = yaml.safe_load(f) or {}
                            if "tasks" in catalog_data:
                                for task in catalog_data["tasks"]:
                                    if "name" not in task:
                                        result.errors.append(f"[Catalog] Task in {fname} missing 'name' field")
                                    if "command" not in task:
                                        result.errors.append(
                                            f"[Catalog] Task '{task.get('name', 'unknown')}' in {fname} missing 'command' field"
                                        )
                                    if "description" not in task:
                                        result.errors.append(
                                            f"[Catalog] Task '{task.get('name', 'unknown')}' in {fname} missing 'description' field"
                                        )
                            if fpath not in result.files_used:
                                result.files_used.append(fpath)
                        except Exception as e:
                            result.errors.append(f"[Catalog] Error loading {fpath}: {e}")
            # Validate catalog groups
            if catalog_groups_exists:
                for fname in os.listdir(catalog_groups_file):
                    if fname.endswith(".yaml") or fname.endswith(".yml"):
                        fpath = os.path.join(catalog_groups_file, fname)
                        try:
                            with open(fpath, "r") as f:
                                catalog_data = yaml.safe_load(f) or {}
                            if "groups" in catalog_data:
                                for group in catalog_data["groups"]:
                                    if "name" not in group:
                                        result.errors.append(f"[Catalog] Group in {fname} missing 'name' field")
                                    if "tasks" not in group:
                                        result.errors.append(
                                            f"[Catalog] Group '{group.get('name', 'unknown')}' in {fname} missing 'tasks' field"
                                        )
                                    if "description" not in group:
                                        result.errors.append(
                                            f"[Catalog] Group '{group.get('name', 'unknown')}' in {fname} missing 'description' field"
                                        )
                            if fpath not in result.files_used:
                                result.files_used.append(fpath)
                        except Exception as e:
                            result.errors.append(f"[Catalog] Error loading {fpath}: {e}")

    except yaml.YAMLError as e:
        result.errors.append(f"YAML syntax error: {e}")
    except Exception as e:
        result.errors.append(f"Error loading config: {e}")

    return result


def _validate_tasks(result):
    """Validate task definitions."""
    config = result.config

    if "tasks" not in config or not config["tasks"]:
        result.errors.append("No tasks defined in config")
        return

    task_names = [s.get("name", "<unnamed_{}>".format(i)) for i, s in enumerate(config["tasks"])]

    # Check for duplicate task names
    if len(task_names) != len(set(task_names)):
        duplicates = [n for n in task_names if task_names.count(n) > 1]
        result.errors.append("Duplicate task names: {}".format(", ".join(set(duplicates))))

    # Note: Required field validation is now done per-file during initial validation
    # to properly group errors by source file

    # Check for unused tasks (if enabled in global config)
    if get_config_value("validation.warn_unused_tasks", True):
        if "groups" in config and config["groups"]:
            used_tasks = set()
            for group in config["groups"]:
                used_tasks.update(group.get("tasks", []))
            unused = set(task_names) - used_tasks
            if unused:
                result.warnings.append("Unused tasks (not in any group): {}".format(", ".join(unused)))


def _validate_groups(result):
    """Validate group definitions."""
    config = result.config

    if "groups" not in config:
        return

    groups = config["groups"]
    group_names = [g.get("name", "<unnamed_{}>".format(i)) for i, g in enumerate(groups)]
    task_names = [s.get("name") for s in config.get("tasks", []) if "name" in s]

    # Check for duplicate group names
    if len(group_names) != len(set(group_names)):
        duplicates = [n for n in group_names if group_names.count(n) > 1]
        result.errors.append("Duplicate group names: {}".format(", ".join(set(duplicates))))

    # Note: Required field validation is now done per-file during initial validation
    # to properly group errors by source file

    # Get group sources for better error messages
    group_sources = config.get("_group_sources", {})

    for group in groups:
        if "name" not in group:
            continue

        group_name = group["name"]
        source_file = group_sources.get(group_name, "unknown file")
        if source_file != "unknown file":
            source_file = os.path.basename(source_file)

        # Check if tasks exist
        if "tasks" in group and group["tasks"]:
            for task_name in group["tasks"]:
                # Check if task_name is a string (common error: using dict instead of string)
                if not isinstance(task_name, str):
                    result.errors.append(
                        "Group '{}' in {} has invalid task entry: expected string, got {}".format(
                            group_name, source_file, type(task_name).__name__
                        )
                    )
                    continue
                if task_name not in task_names:
                    result.errors.append("Group '{}' references non-existent task '{}'".format(group_name, task_name))

        # Validate schedule if present
        if "schedule" in group:
            try:
                schedule = group["schedule"]
                # Support both string format and dict format with 'cron' key
                if isinstance(schedule, dict):
                    if "cron" in schedule:
                        schedule_str = schedule["cron"]
                    else:
                        result.errors.append(
                            "Group '{}' in {} has schedule dict without 'cron' key".format(group_name, source_file)
                        )
                        continue
                elif isinstance(schedule, str):
                    schedule_str = schedule
                else:
                    result.errors.append(
                        "Group '{}' in {} has invalid schedule type: expected string or dict, got {}".format(
                            group_name, source_file, type(schedule).__name__
                        )
                    )
                    continue
                
                parts = schedule_str.split()
                if len(parts) != 5:
                    result.warnings.append(
                        "Group '{}' in {} schedule may be invalid: '{}' (expected 5 cron fields)".format(
                            group_name, source_file, schedule_str
                        )
                    )
            except Exception as e:
                result.errors.append(
                    "Group '{}' in {} has invalid schedule: {}".format(group_name, source_file, e)
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
