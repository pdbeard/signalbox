"""
Helper utilities for signalbox to reduce code duplication.
"""

import os
import re
from typing import Dict

import click
import yaml

from .exceptions import ConfigurationError

# Task and group names become directory and file names (logs/<task>/,
# signalbox-<group>.service), so they are restricted to a safe character set.
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*$")


def load_yaml_files_from_dir(directory: str, key: str, suppress_warnings: bool = False) -> list:
    """
    Load the `key` entries from every YAML file in a directory, in filename order.

    Hidden files (editor swap files, .DS_Store, etc.) are skipped. A file that
    fails to load is reported as a warning and skipped.

    Returns:
        List of dicts: [{"data": item, "source": filepath}, ...]
    """
    # Allow global suppression via env var
    if os.environ.get("SIGNALBOX_SUPPRESS_CONFIG_WARNINGS", "0") == "1":
        suppress_warnings = True

    items = []

    if not os.path.exists(directory):
        return items

    for filename in sorted(os.listdir(directory)):
        if filename.startswith(".") or not filename.endswith((".yaml", ".yml")):
            continue
        filepath = os.path.join(directory, filename)

        try:
            with open(filepath, "r") as f:
                data = yaml.safe_load(f)
                if data and key in data:
                    items_from_file = data[key] if isinstance(data[key], list) else [data[key]]
                    items.extend({"data": item, "source": filepath} for item in items_from_file)
        except Exception as e:
            if not suppress_warnings:
                click.echo(f"Warning: Cannot load {filepath}: {e}", err=True)

    return items


def load_yaml_dict_from_dir(directory: str, key: str, filename_prefix: str = "") -> Dict:
    """
    Load and merge the `key` mappings from YAML files in a directory.

    Similar to load_yaml_files_from_dir but merges dictionaries instead
    of extending lists. Used for runtime state loading.

    Args:
        directory: Path to directory containing YAML files
        key: Key to extract from each YAML file (e.g., 'tasks', 'groups')
        filename_prefix: Only process files starting with this prefix

    Returns:
        Merged dictionary from all matching YAML files
    """
    merged_dict = {}

    if not os.path.exists(directory):
        return merged_dict

    for filename in sorted(os.listdir(directory)):
        # Skip hidden files (editor swap files, .DS_Store, etc.)
        if filename.startswith("."):
            continue

        if filename_prefix and not filename.startswith(filename_prefix):
            continue

        if not filename.endswith((".yaml", ".yml")):
            continue

        filepath = os.path.join(directory, filename)

        try:
            with open(filepath, "r") as f:
                data = yaml.safe_load(f)
                if data and key in data:
                    if isinstance(data[key], dict):
                        merged_dict.update(data[key])
        except Exception as e:
            click.echo(f"Warning: Cannot load {filepath}: {e}", err=True)

    return merged_dict


def get_resolved_log_dir() -> str:
    """
    Resolve the configured log directory to an absolute path.

    Centralizes the resolution logic used across alerts.py and log_manager.py
    so both modules read from the same location regardless of working directory
    or SIGNALBOX_HOME / XDG_CONFIG_HOME settings.

    Returns:
        Absolute path to the log directory
    """
    from .config import get_config_value, _default_config_manager

    log_dir = get_config_value("paths.log_dir", "logs")
    if not os.path.isabs(log_dir):
        config_home = _default_config_manager.find_config_home()
        log_dir = os.path.join(config_home, log_dir)
    return log_dir


def get_timestamp_format() -> str:
    """
    Get the configured timestamp format.

    Centralized function to avoid hardcoding '%Y%m%d_%H%M%S_%f' everywhere.

    Returns:
        Timestamp format string from config, or default
    """
    from .config import get_config_value

    return get_config_value("logging.timestamp_format", "%Y%m%d_%H%M%S_%f")


def format_timestamp(dt) -> str:
    """
    Format a datetime object using the configured timestamp format.

    Args:
        dt: datetime object to format

    Returns:
        Formatted timestamp string
    """
    return dt.strftime(get_timestamp_format())


def parse_timestamp(timestamp_str: str):
    """
    Parse a timestamp string using the configured format.

    Args:
        timestamp_str: Timestamp string to parse

    Returns:
        datetime object, or None if parsing fails
    """
    from datetime import datetime

    try:
        # Remove .log extension if present
        timestamp_str = timestamp_str.replace(".log", "")
        return datetime.strptime(timestamp_str, get_timestamp_format())
    except ValueError:
        return None


def is_valid_name(name) -> bool:
    """Return True if name is safe to use as a task or group name."""
    return isinstance(name, str) and bool(NAME_PATTERN.match(name))


def check_name(name, kind="task"):
    """Raise ConfigurationError unless name is a safe task/group name.

    Names are used to build paths, so anything containing a path separator
    or '..' could read, write or delete files outside the log directory.
    """
    if not is_valid_name(name):
        raise ConfigurationError(
            f"Invalid {kind} name {name!r}: use only letters, digits, '_', '-' and '.', "
            "and do not start with '.' or '-'"
        )
    return name
