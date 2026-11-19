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
NAME_RULE = "use only letters, digits, '_', '-' and '.', and do not start with '.' or '-'"


def yaml_files(directory):
    """Names of the YAML files in a directory, sorted; hidden files (editor swap files, .DS_Store) are skipped.

    The one rule for which files count as config, shared by the loaders and `signalbox validate`.
    """
    if not os.path.isdir(directory):
        return []
    return [f for f in sorted(os.listdir(directory)) if not f.startswith(".") and f.endswith((".yaml", ".yml"))]


def load_yaml_files_from_dir(directory: str, key: str, suppress_warnings: bool = False, errors=None) -> list:
    """
    Load the `key` entries from every YAML file in a directory, in filename order.

    Hidden files (editor swap files, .DS_Store, etc.) are skipped. A file that
    fails to load is reported as a warning and skipped; if `errors` is a dict,
    errors[filepath] = message is added so callers can report the failure.

    Returns:
        List of dicts: [{"data": item, "source": filepath}, ...]
    """
    items = []
    for filename in yaml_files(directory):
        filepath = os.path.join(directory, filename)

        try:
            with open(filepath, "r") as f:
                data = yaml.safe_load(f)
                if data and key in data:
                    items_from_file = data[key] if isinstance(data[key], list) else [data[key]]
                    items.extend({"data": item, "source": filepath} for item in items_from_file)
        except Exception as e:
            if errors is not None:
                errors[filepath] = str(e)
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
    for filename in yaml_files(directory):
        if not filename.startswith(filename_prefix):
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
    """The configured log directory, resolved like every other path setting (used by alerts.py and log_manager.py)."""
    from .config import get_config_value, resolve_path

    return resolve_path(get_config_value("paths.log_dir", "logs"))


# Log file names, runtime last_run values and alert timestamps all use this
# format. It is fixed rather than configurable: microseconds keep runs that
# start in the same second (two cron jobs at :00) from sharing a log file, and
# a '/' would turn the name into directories that do not exist.
TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S_%f"


def format_timestamp(dt) -> str:
    """
    Format a datetime object as a signalbox timestamp.

    Args:
        dt: datetime object to format

    Returns:
        Formatted timestamp string
    """
    return dt.strftime(TIMESTAMP_FORMAT)


def parse_timestamp(timestamp_str: str):
    """
    Parse a signalbox timestamp string.

    Args:
        timestamp_str: Timestamp string to parse

    Returns:
        datetime object, or None if parsing fails
    """
    from datetime import datetime

    try:
        # Remove .log extension if present
        timestamp_str = timestamp_str.replace(".log", "")
        return datetime.strptime(timestamp_str, TIMESTAMP_FORMAT)
    except ValueError:
        return None


def display_time(timestamp):
    """A signalbox timestamp formatted with display.date_format; values that do not parse are shown as-is."""
    from .config import get_config_value

    dt = parse_timestamp(str(timestamp)) if timestamp else None
    if dt is None:
        return timestamp or ""
    try:
        return dt.strftime(get_config_value("display.date_format", "%Y-%m-%d %H:%M:%S"))
    except (TypeError, ValueError):
        return timestamp


def is_valid_name(name) -> bool:
    """Return True if name is safe to use as a task or group name."""
    return isinstance(name, str) and bool(NAME_PATTERN.match(name))


def check_name(name, kind="task"):
    """Raise ConfigurationError unless name is a safe task/group name.

    Names are used to build paths, so anything containing a path separator
    or '..' could read, write or delete files outside the log directory.
    """
    if not is_valid_name(name):
        raise ConfigurationError(f"Invalid {kind} name {name!r}: {NAME_RULE}")
    return name


# A valid environment variable name (POSIX shells accept only these)
ENV_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Shorter values are not masked: masking "1" or "on" would hide ordinary output
MIN_SECRET_LENGTH = 4

# Variables whose names look like this are masked without being listed in 'mask' (the same idea as Django's
# settings filter); ordinary settings such as BACKUP_DIR stay readable in the logs
SECRET_NAME_PATTERN = re.compile(r"TOKEN|SECRET|PASS|KEY|AUTH|CREDENTIAL|SIGNATURE", re.IGNORECASE)


def load_env_file(path):
    """Read KEY=VALUE lines from an env file into a dict.

    Blank lines and lines that start with '#' are skipped, an 'export ' prefix
    is allowed, and one pair of matching quotes around a value is removed.
    Values are used as written: no variable expansion and no escapes.

    Raises:
        ConfigurationError: if the file does not exist or a line is not KEY=VALUE
    """
    if not os.path.isfile(path):
        raise ConfigurationError(f"env_file not found: {path}")
    values = {}
    with open(path, "r", encoding="utf-8") as f:
        for number, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].lstrip()
            key, sep, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if not sep or not ENV_NAME_PATTERN.match(key):
                raise ConfigurationError(f"{path}, line {number}: expected KEY=VALUE")
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key] = value
    return values


def mask_secrets(text, secrets):
    """Replace each secret value in text with *****. Longest first, so a secret inside another is not half-masked."""
    for secret in sorted({s for s in secrets if len(s) >= MIN_SECRET_LENGTH}, key=len, reverse=True):
        text = text.replace(secret, "*****")
    return text


# The platforms signalbox runs on, as platform.system().lower() names them
PLATFORMS = ("darwin", "linux")


def current_platform():
    import platform

    return platform.system().lower()


def on_this_platform(entry):
    """True unless the task has 'platforms' and this machine is not one of them."""
    platforms = entry.get("platforms") if isinstance(entry, dict) else None
    return not platforms or current_platform() in platforms
