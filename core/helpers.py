"""
Helper utilities for signalbox to reduce code duplication.
"""

import os
import yaml
import click
from typing import Dict, List, Optional, Callable


def load_yaml_files_from_dir(
    directory: str,
    key: str,
    filter_func: Optional[Callable[[str], bool]] = None,
    filename_prefix: str = "",
    filename_suffix: tuple = (".yaml", ".yml"),
    track_sources: bool = False,
    suppress_warnings: bool = False,
) -> list:
    import os

    # Allow global suppression via env var
    if os.environ.get("SIGNALBOX_SUPPRESS_CONFIG_WARNINGS", "0") == "1":
        suppress_warnings = True
    """
    Load and merge YAML files from a directory.
    
    This is a generic helper to reduce duplication across config loading
    patterns in config.py and runtime.py.
    
    Args:
        directory: Path to directory containing YAML files
        key: Key to extract from each YAML file (e.g., 'tasks', 'groups')
        filter_func: Optional function to filter filenames (returns True to include)
        filename_prefix: Only process files starting with this prefix
        filename_suffix: Tuple of file extensions to process (default: .yaml, .yml)
        track_sources: If True, return dicts with 'data' and 'source' keys
        
    Returns:
        List of items extracted from all matching YAML files.
        If track_sources=True, returns list of dicts: [{"data": item, "source": filepath}, ...]
        If track_sources=False, returns flat list of items: [item1, item2, ...]
        
    Example:
        # Load all tasks from config/tasks directory (flat list)
        tasks = load_yaml_files_from_dir(
            "config/tasks", 
            "tasks",
            filter_func=lambda f: not f.startswith(".")
        )

        # Load tasks with source tracking
        tasks = load_yaml_files_from_dir(
            "config/tasks",
            "tasks",
            track_sources=True
        )
        # Returns: [{"data": {...}, "source": "path/to/file.yaml"}, ...]
    """
    items = []

    if not os.path.exists(directory):
        return items


    for filename in sorted(os.listdir(directory)):
        filepath = os.path.join(directory, filename)
        # Skip files in build/ directory
        if 'build' in filepath.split(os.sep):
            continue

        # Apply filters
        if filename_prefix and not filename.startswith(filename_prefix):
            continue

        if not filename.endswith(filename_suffix):
            continue

        if filter_func and not filter_func(filename):
            continue

        try:
            with open(filepath, "r") as f:
                data = yaml.safe_load(f)
                if data and key in data:
                    items_from_file = data[key] if isinstance(data[key], list) else [data[key]]
                    if track_sources:
                        for item in items_from_file:
                            items.append({"data": item, "source": filepath})
                    else:
                        items.extend(items_from_file)
        except Exception as e:
            if not suppress_warnings:
                click.echo(f"Warning: Failed to load {filepath}: {e}", err=True)

    return items


def load_yaml_dict_from_dir(
    directory: str,
    key: str,
    filter_func: Optional[Callable[[str], bool]] = None,
    filename_prefix: str = "",
    filename_suffix: str = (".yaml", ".yml"),
) -> Dict:
    """
    Load and merge YAML files from a directory into a dictionary.

    Similar to load_yaml_files_from_dir but merges dictionaries instead
    of extending lists. Useful for runtime state loading.

    Args:
        directory: Path to directory containing YAML files
        key: Key to extract from each YAML file (e.g., 'tasks', 'groups')
        filter_func: Optional function to filter filenames
        filename_prefix: Only process files starting with this prefix
        filename_suffix: Tuple of file extensions to process

    Returns:
        Merged dictionary from all matching YAML files

    Example:
        # Load runtime state
        runtime_tasks = load_yaml_dict_from_dir(
            "runtime/tasks",
            "tasks",
            filename_prefix="runtime_"
        )
    """
    merged_dict = {}

    if not os.path.exists(directory):
        return merged_dict

    for filename in sorted(os.listdir(directory)):
        # Apply filters
        if filename_prefix and not filename.startswith(filename_prefix):
            continue

        if not filename.endswith(filename_suffix):
            continue

        if filter_func and not filter_func(filename):
            continue

        filepath = os.path.join(directory, filename)

        try:
            with open(filepath, "r") as f:
                data = yaml.safe_load(f)
                if data and key in data:
                    if isinstance(data[key], dict):
                        merged_dict.update(data[key])
        except Exception as e:
            click.echo(f"Warning: Failed to load {filepath}: {e}", err=True)

    return merged_dict


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
