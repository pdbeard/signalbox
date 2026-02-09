"""
Pytest fixtures for signalbox tests.

This module provides shared fixtures used across test modules.
"""

import pytest
import tempfile
import shutil
import yaml
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory that is cleaned up after the test."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)


@pytest.fixture
def temp_config_dir(temp_dir):
    """
    Create a temporary signalbox configuration directory structure.

    Returns the path to the config home directory with the following structure:
    temp_config_dir/
    ├── config/
    │   ├── signalbox.yaml
    │   ├── scripts/
    │   └── groups/
    ├── logs/
    └── runtime/
        ├── scripts/
        └── groups/
    """
    config_dir = Path(temp_dir)

    # Create directory structure
    (config_dir / "config").mkdir()
    (config_dir / "config" / "tasks").mkdir()
    (config_dir / "config" / "groups").mkdir()
    (config_dir / "logs").mkdir()
    (config_dir / "runtime").mkdir()
    (config_dir / "runtime" / "tasks").mkdir()
    (config_dir / "runtime" / "groups").mkdir()

    yield str(config_dir)


@pytest.fixture
def sample_signalbox_yaml(temp_config_dir):
    """Create a sample signalbox.yaml configuration file."""
    config_file = Path(temp_config_dir) / "config" / "signalbox.yaml"

    config_data = {
        "default_log_limit": {"type": "count", "value": 10},
        "paths": {
            "log_dir": "logs",
            "tasks_file": "config/tasks",
            "groups_file": "config/groups",
        },
        "execution": {
            "default_timeout": 300,
            "capture_stdout": True,
            "capture_stderr": True,
            "max_parallel_workers": 5,
        },
        "logging": {"timestamp_format": "%Y%m%d_%H%M%S_%f"},
        "display": {"date_format": "%Y-%m-%d %H:%M:%S"},
    }

    with open(config_file, "w") as f:
        yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)

    return str(config_file)


@pytest.fixture
def sample_scripts_yaml(temp_config_dir):
    """Create sample script YAML files."""
    tasks_dir = Path(temp_config_dir) / "config" / "tasks"

    # Create basic.yaml
    basic_tasks = {
        "tasks": [
            {
                "name": "hello",
                "command": 'echo "Hello World"',
                "description": "Simple echo task",
                "log_limit": {"type": "count", "value": 5},
            },
            {
                "name": "show_date",
                "command": "date",
                "description": "Show current date",
            },
        ]
    }

    basic_file = tasks_dir / "basic.yaml"
    with open(basic_file, "w") as f:
        yaml.dump(basic_tasks, f, default_flow_style=False, sort_keys=False)

    # Create system.yaml
    system_tasks = {
        "tasks": [
            {
                "name": "uptime",
                "command": "uptime",
                "description": "Show system uptime",
            }
        ]
    }

    system_file = tasks_dir / "system.yaml"
    with open(system_file, "w") as f:
        yaml.dump(system_tasks, f, default_flow_style=False, sort_keys=False)

    return [str(basic_file), str(system_file)]


@pytest.fixture
def sample_groups_yaml(temp_config_dir):
    """Create sample group YAML files."""
    groups_dir = Path(temp_config_dir) / "config" / "groups"

    groups_data = {
        "groups": [
            {
                "name": "basic",
                "description": "Basic test group",
                "tasks": ["hello", "show_date"],
                "execution": {"mode": "serial"},
            },
            {
                "name": "parallel_test",
                "description": "Parallel execution test",
                "tasks": ["hello", "uptime"],
                "execution": {"mode": "parallel"},
            },
        ]
    }

    groups_file = groups_dir / "test.yaml"
    with open(groups_file, "w") as f:
        yaml.dump(groups_data, f, default_flow_style=False, sort_keys=False)

    return str(groups_file)


@pytest.fixture
def full_config(temp_config_dir, sample_signalbox_yaml, sample_scripts_yaml, sample_groups_yaml):
    """
    Create a complete signalbox configuration with all files.

    Returns the path to the config home directory.
    """
    return temp_config_dir


@pytest.fixture
def empty_config_dir(temp_dir):
    """Create an empty config directory without any YAML files."""
    config_dir = Path(temp_dir)
    (config_dir / "config").mkdir()
    return str(config_dir)
