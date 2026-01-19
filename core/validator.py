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
        scripts_file = get_config_value("paths.scripts_file", "config/scripts")
        groups_file = get_config_value("paths.groups_file", "config/groups")
        catalog_scripts_file = get_config_value("paths.catalog_scripts_file", "config/catalog/scripts")
        catalog_groups_file = get_config_value("paths.catalog_groups_file", "config/catalog/groups")
        
        # Resolve all paths to absolute paths
        scripts_file = resolve_path(scripts_file)
        groups_file = resolve_path(groups_file)
        catalog_scripts_file = resolve_path(catalog_scripts_file)
        catalog_groups_file = resolve_path(catalog_groups_file)

        # Strictly validate all user script YAML files for syntax and required fields (user and catalog)
        for script_dir in [scripts_file, catalog_scripts_file]:
            is_catalog = (script_dir == catalog_scripts_file)
            if os.path.isdir(script_dir):
                for fname in os.listdir(script_dir):
                    if fname.endswith('.yaml') or fname.endswith('.yml'):
                        fpath = os.path.join(script_dir, fname)
                        file_errors = []
                        try:
                            with open(fpath, 'r') as f:
                                data = yaml.safe_load(f)
                            if not data or 'scripts' not in data:
                                file_errors.append(f"No 'scripts' key found")
                            else:
                                for script in data['scripts']:
                                    if 'name' not in script:
                                        file_errors.append(f"Script missing 'name' field")
                                    if 'command' not in script:
                                        file_errors.append(f"Script '{script.get('name', 'unknown')}' missing 'command' field")
                                    if 'description' not in script:
                                        file_errors.append(f"Script '{script.get('name', 'unknown')}' missing 'description' field")
                                    # Validate alerts field if present
                                    if 'alerts' in script:
                                        alerts_list = script['alerts']
                                        if not isinstance(alerts_list, list):
                                            file_errors.append(f"Script '{script.get('name', 'unknown')}' alerts field must be a list")
                                        else:
                                            for idx, alert in enumerate(alerts_list):
                                                if not isinstance(alert, dict):
                                                    file_errors.append(f"Script '{script.get('name', 'unknown')}' alert #{idx+1} must be a dict")
                                                    continue
                                                if 'pattern' not in alert:
                                                    file_errors.append(f"Script '{script.get('name', 'unknown')}' alert #{idx+1} missing 'pattern' field")
                                                if 'message' not in alert:
                                                    file_errors.append(f"Script '{script.get('name', 'unknown')}' alert #{idx+1} missing 'message' field")
                                                # Validate severity if present
                                                if 'severity' in alert and alert['severity'] not in ['info', 'warning', 'critical']:
                                                    file_errors.append(f"Script '{script.get('name', 'unknown')}' alert #{idx+1} has invalid severity (must be info, warning, or critical)")

                        except yaml.YAMLError as e:
                            file_errors.append(f"YAML syntax error: {e}")
                        except Exception as e:
                            file_errors.append(f"Error loading: {e}")
                        if file_errors:
                            prefix = "[Catalog] " if is_catalog else ""
                            result.errors.append(f"\n{prefix}Script Config File:  {fname}")
                            for err in file_errors:
                                result.errors.append(f"{prefix}{err}")

        # Strictly validate all user group YAML files for syntax and required fields (user and catalog)
        for group_dir in [groups_file, catalog_groups_file]:
            is_catalog = (group_dir == catalog_groups_file)
            if os.path.isdir(group_dir):
                for fname in os.listdir(group_dir):
                    if fname.endswith('.yaml') or fname.endswith('.yml'):
                        fpath = os.path.join(group_dir, fname)
                        file_errors = []
                        try:
                            with open(fpath, 'r') as f:
                                data = yaml.safe_load(f)
                            if not data or 'groups' not in data:
                                file_errors.append(f"No 'groups' key found")
                            else:
                                for group in data['groups']:
                                    if 'name' not in group:
                                        file_errors.append(f"Group missing 'name' field")
                                    if 'description' not in group:
                                        file_errors.append(f"Group '{group.get('name', 'unknown')}' missing 'description' field")
                                    if 'scripts' not in group:
                                        file_errors.append(f"Group '{group.get('name', 'unknown')}' missing 'scripts' field")
                        except yaml.YAMLError as e:
                            file_errors.append(f"YAML syntax error: {e}")
                        except Exception as e:
                            file_errors.append(f"Error loading: {e}")
                        if file_errors:
                            prefix = "[Catalog] " if is_catalog else ""
                            result.errors.append(f"\n{prefix}Group Config File:  {fname}")
                            for err in file_errors:
                                result.errors.append(f"{prefix}{err}")
        # Validate user scripts/groups, fallback to catalog if enabled
        user_scripts_exists = os.path.isdir(scripts_file) and any(f.endswith(('.yaml', '.yml')) for f in os.listdir(scripts_file)) if os.path.exists(scripts_file) else False
        user_groups_exists = os.path.isdir(groups_file) and any(f.endswith(('.yaml', '.yml')) for f in os.listdir(groups_file)) if os.path.exists(groups_file) else False
        catalog_scripts_exists = os.path.isdir(catalog_scripts_file) and any(f.endswith(('.yaml', '.yml')) for f in os.listdir(catalog_scripts_file)) if os.path.exists(catalog_scripts_file) else False
        catalog_groups_exists = os.path.isdir(catalog_groups_file) and any(f.endswith(('.yaml', '.yml')) for f in os.listdir(catalog_groups_file)) if os.path.exists(catalog_groups_file) else False

        if not user_scripts_exists and include_catalog and catalog_scripts_exists:
            # Use catalog scripts as config source
            result.config = {"scripts": [], "groups": []}
            # Load all catalog scripts
            for fname in os.listdir(catalog_scripts_file):
                if fname.endswith('.yaml') or fname.endswith('.yml'):
                    fpath = os.path.join(catalog_scripts_file, fname)
                    try:
                        with open(fpath, 'r') as f:
                            catalog_data = yaml.safe_load(f) or {}
                        if 'scripts' in catalog_data:
                            result.config['scripts'].extend(catalog_data['scripts'])
                        result.files_used.append(fpath)
                    except Exception as e:
                        result.errors.append(f"[Catalog] Error loading {fpath}: {e}")
            # Load all catalog groups
            if catalog_groups_exists:
                for fname in os.listdir(catalog_groups_file):
                    if fname.endswith('.yaml') or fname.endswith('.yml'):
                        fpath = os.path.join(catalog_groups_file, fname)
                        try:
                            with open(fpath, 'r') as f:
                                catalog_data = yaml.safe_load(f) or {}
                            if 'groups' in catalog_data:
                                if 'groups' not in result.config:
                                    result.config['groups'] = []
                                result.config['groups'].extend(catalog_data['groups'])
                            result.files_used.append(fpath)
                        except Exception as e:
                            result.errors.append(f"[Catalog] Error loading {fpath}: {e}")
            # Validate as normal
            _validate_scripts(result)
            _validate_groups(result)
            _validate_global_config(result)
        elif not user_scripts_exists:
            result.errors.append(f"No scripts file found ({scripts_file})")
            return result
        else:
            result.config = load_config()
            # Track which files are being used
            config_file = resolve_path("config/signalbox.yaml")
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

        # Optionally validate catalog scripts/groups (for extra checking, not as primary source)
        if include_catalog and user_scripts_exists:
            # Validate catalog scripts
            if catalog_scripts_exists:
                for fname in os.listdir(catalog_scripts_file):
                    if fname.endswith('.yaml') or fname.endswith('.yml'):
                        fpath = os.path.join(catalog_scripts_file, fname)
                        try:
                            with open(fpath, 'r') as f:
                                catalog_data = yaml.safe_load(f) or {}
                            if 'scripts' in catalog_data:
                                for script in catalog_data['scripts']:
                                    if 'name' not in script:
                                        result.errors.append(f"[Catalog] Script in {fname} missing 'name' field")
                                    if 'command' not in script:
                                        result.errors.append(f"[Catalog] Script '{script.get('name', 'unknown')}' in {fname} missing 'command' field")
                                    if 'description' not in script:
                                        result.errors.append(f"[Catalog] Script '{script.get('name', 'unknown')}' in {fname} missing 'description' field")
                            if fpath not in result.files_used:
                                result.files_used.append(fpath)
                        except Exception as e:
                            result.errors.append(f"[Catalog] Error loading {fpath}: {e}")
            # Validate catalog groups
            if catalog_groups_exists:
                for fname in os.listdir(catalog_groups_file):
                    if fname.endswith('.yaml') or fname.endswith('.yml'):
                        fpath = os.path.join(catalog_groups_file, fname)
                        try:
                            with open(fpath, 'r') as f:
                                catalog_data = yaml.safe_load(f) or {}
                            if 'groups' in catalog_data:
                                for group in catalog_data['groups']:
                                    if 'name' not in group:
                                        result.errors.append(f"[Catalog] Group in {fname} missing 'name' field")
                                    if 'scripts' not in group:
                                        result.errors.append(f"[Catalog] Group '{group.get('name', 'unknown')}' in {fname} missing 'scripts' field")
                                    if 'description' not in group:
                                        result.errors.append(f"[Catalog] Group '{group.get('name', 'unknown')}' in {fname} missing 'description' field")
                            if fpath not in result.files_used:
                                result.files_used.append(fpath)
                        except Exception as e:
                            result.errors.append(f"[Catalog] Error loading {fpath}: {e}")

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

    script_names = [s.get("name", f"<unnamed_{i}>") for i, s in enumerate(config["scripts"])]

    # Check for duplicate script names
    if len(script_names) != len(set(script_names)):
        duplicates = [n for n in script_names if script_names.count(n) > 1]
        result.errors.append(f"Duplicate script names: {', '.join(set(duplicates))}")

    # Note: Required field validation is now done per-file during initial validation
    # to properly group errors by source file

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
    group_names = [g.get("name", f"<unnamed_{i}>") for i, g in enumerate(groups)]
    script_names = [s.get("name") for s in config.get("scripts", []) if "name" in s]

    # Check for duplicate group names
    if len(group_names) != len(set(group_names)):
        duplicates = [n for n in group_names if group_names.count(n) > 1]
        result.errors.append(f"Duplicate group names: {', '.join(set(duplicates))}")

    # Note: Required field validation is now done per-file during initial validation
    # to properly group errors by source file

    for group in groups:
        if "name" not in group:
            continue

        group_name = group["name"]

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
