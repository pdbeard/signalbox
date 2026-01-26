import yaml


def test_custom_log_dir(tmp_path):
    # Create a custom config with a unique log_dir (absolute paths)
    custom_log_dir = tmp_path / "mylogs"
    scripts_dir = tmp_path / "scripts"
    groups_dir = tmp_path / "groups"
    scripts_dir.mkdir()
    config = {
        "paths": {
            "log_dir": str(custom_log_dir.resolve()),
            "scripts_file": str(scripts_dir.resolve()),
            "groups_file": str(groups_dir.resolve()),
        },
        "scripts": [{"name": "hello", "command": "echo hi", "description": "test"}],
    }
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "signalbox.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config, f)
    # Create script file
    with open(scripts_dir / "test.yaml", "w") as f:
        yaml.dump({"scripts": config["scripts"]}, f)
    try:
        import sys
        import os

        os.environ["SIGNALBOX_HOME"] = str(tmp_path)
        sys.modules.pop("core.config", None)
        sys.modules.pop("core.cli_commands", None)
        from core.cli_commands import cli
        from core import config

        config.reset_config()

        from click.testing import CliRunner
        from unittest.mock import patch
        runner = CliRunner()
        # Patch core.config.load_config to return our test config dict, not the config module
        test_config_dict = {
            "scripts": [{"name": "hello", "command": "echo hi", "description": "test"}],
            "groups": [],
            "_script_sources": {"hello": str(scripts_dir / "test.yaml")},
            "_group_sources": {},
        }
        with patch("core.config.load_config", return_value=test_config_dict):
            result = runner.invoke(cli, ["--config", str(config_file), "run", "hello"])
        print("CLI output:", result.output)
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        log_dir = custom_log_dir / "hello"
        assert log_dir.exists(), f"Log dir does not exist: {log_dir}"
        log_files = list(log_dir.glob("*.log"))
        assert log_files, f"No log files found in custom log_dir: {log_dir}"
    finally:
        import shutil

        shutil.rmtree(str(custom_log_dir), ignore_errors=True)
        shutil.rmtree(str(scripts_dir), ignore_errors=True)
        shutil.rmtree(str(groups_dir), ignore_errors=True)
        shutil.rmtree(str(config_dir), ignore_errors=True)
