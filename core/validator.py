# Configuration validation for signalbox

import os
import yaml
from .config import load_config, get_config_value, load_global_config


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


def validate_configuration():
    """Validate all configuration files.

    Returns:
            ValidationResult: Object containing validation results
    """
    result = ValidationResult()

    try:
        # Check if files exist
        scripts_file = get_config_value("paths.scripts_file", "scripts")
        groups_file = get_config_value("paths.groups_file", "groups")

        if not os.path.exists(scripts_file):
            result.errors.append(f"No scripts file found ({scripts_file})")
            return result

        result.config = load_config()

        # Track which files are being used
        config_file = "config/signalbox.yaml"
        if os.path.exists(config_file):
            result.files_used.append(f"{config_file} (global config)")
        if os.path.exists(scripts_file):
            result.files_used.append(scripts_file)
        if os.path.exists(groups_file):
            result.files_used.append(groups_file)

        # Validate scripts
        _validate_scripts(result)

        # Validate groups
        _validate_groups(result)

        # Validate global config
        _validate_global_config(result)

    except yaml.YAMLError as e:
        result.errors.append(f"YAML syntax error: {e}")
    except Exception as e:
        result.errors.append(f"Error loading config: {e}")

    return result


def _validate_scripts(result):
    """Validate script definitions."""
    config = result.config

    if "scripts" not in config or not config["scripts"]:
        result.errors.append("No scripts defined in config")
        return

    script_names = [s["name"] for s in config["scripts"]]

    # Check for duplicate script names
    if len(script_names) != len(set(script_names)):
        duplicates = [n for n in script_names if script_names.count(n) > 1]
        result.errors.append(f"Duplicate script names: {', '.join(set(duplicates))}")

    # Check required fields
    for script in config["scripts"]:
        if "name" not in script:
            result.errors.append("Script missing 'name' field")
        if "command" not in script:
            result.errors.append(f"Script '{script.get('name', 'unknown')}' missing 'command' field")

    # Check for unused scripts (if enabled in global config)
    if get_config_value("validation.warn_unused_scripts", True):
        if "groups" in config and config["groups"]:
            used_scripts = set()
            for group in config["groups"]:
                used_scripts.update(group.get("scripts", []))
            unused = set(script_names) - used_scripts
            if unused:
                result.warnings.append(f"Unused scripts (not in any group): {', '.join(unused)}")


def _validate_groups(result):
    """Validate group definitions."""
    config = result.config

    if "groups" not in config:
        return

    groups = config["groups"]
    group_names = [g["name"] for g in groups]
    script_names = [s["name"] for s in config.get("scripts", [])]

    # Check for duplicate group names
    if len(group_names) != len(set(group_names)):
        duplicates = [n for n in group_names if group_names.count(n) > 1]
        result.errors.append(f"Duplicate group names: {', '.join(set(duplicates))}")

    for group in groups:
        if "name" not in group:
            result.errors.append("Group missing 'name' field")
            continue

        group_name = group["name"]

        # Check for empty groups (if enabled in global config)
        if get_config_value("validation.warn_empty_groups", True):
            if "scripts" not in group or not group["scripts"]:
                result.warnings.append(f"Group '{group_name}' has no scripts")

        # Check if scripts exist
        if "scripts" in group and group["scripts"]:
            for script_name in group["scripts"]:
                if script_name not in script_names:
                    result.errors.append(f"Group '{group_name}' references non-existent script '{script_name}'")

        # Validate schedule if present
        if "schedule" in group:
            schedule = group["schedule"]
            parts = schedule.split()
            if len(parts) != 5:
                result.warnings.append(
                    f"Group '{group_name}' schedule may be invalid: '{schedule}' (expected 5 fields)"
                )


def _validate_global_config(result):
    """Validate global configuration settings."""
    result.global_config = load_global_config()

    if not result.global_config:
        return

    # Validate timeout value
    timeout = get_config_value("execution.default_timeout", 300)
    if not isinstance(timeout, (int, float)) or timeout < 0:
        result.warnings.append(f"Invalid timeout value: {timeout} (should be >= 0)")


def get_validation_summary(result):
    """Get a summary of the configuration.

    Returns:
            dict: Summary statistics about the configuration
    """
    if not result.config:
        return {}

    script_count = len(result.config.get("scripts", []))
    group_count = len(result.config.get("groups", []))
    scheduled_count = len([g for g in result.config.get("groups", []) if "schedule" in g])

    summary = {"scripts": script_count, "groups": group_count, "scheduled_groups": scheduled_count}

    if result.global_config:
        summary["default_timeout"] = get_config_value("execution.default_timeout", 300)
        summary["default_log_limit"] = get_config_value("default_log_limit", {})

    return summary
