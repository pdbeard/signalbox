import os

import yaml
from click.testing import CliRunner
from unittest.mock import patch


def test_custom_log_dir(tmp_path):
    # Create a custom config with a unique log_dir (absolute paths)
    custom_log_dir = tmp_path / "mylogs"
    tasks_dir = tmp_path / "tasks"
    groups_dir = tmp_path / "groups"
    tasks_dir.mkdir()
    config_data = {
        "paths": {
            "log_dir": str(custom_log_dir.resolve()),
            "tasks_file": str(tasks_dir.resolve()),
            "groups_file": str(groups_dir.resolve()),
        },
    }
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "signalbox.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    # Create task file
    tasks = [{"name": "hello", "command": "echo hi", "description": "test"}]
    with open(tasks_dir / "test.yaml", "w") as f:
        yaml.dump({"tasks": tasks}, f)

    from signalbox import config
    from signalbox.cli import cli

    old_home = os.environ.get("SIGNALBOX_HOME")
    os.environ["SIGNALBOX_HOME"] = str(tmp_path)
    config.reset_config()
    try:
        runner = CliRunner()
        test_config_dict = {
            "tasks": tasks,
            "groups": [],
            "_task_sources": {"hello": str(tasks_dir / "test.yaml")},
            "_group_sources": {},
        }
        with patch("signalbox.commands.task.load_config", return_value=test_config_dict):
            result = runner.invoke(cli, ["--config", str(config_file), "run", "hello"])
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        log_dir = custom_log_dir / "hello"
        assert log_dir.exists(), f"Log dir does not exist: {log_dir}"
        log_files = list(log_dir.glob("*.log"))
        assert log_files, f"No log files found in custom log_dir: {log_dir}"
    finally:
        if old_home is None:
            os.environ.pop("SIGNALBOX_HOME", None)
        else:
            os.environ["SIGNALBOX_HOME"] = old_home
        config.reset_config()
