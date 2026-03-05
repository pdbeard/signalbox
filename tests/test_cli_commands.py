"""
Tests for core.cli_commands module.

Tests CLI command functionality including list, run, run-group, logs,
validation, and other commands. All commands are invoked through the
top-level `cli` group using CliRunner for correctness.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, mock_open

from core.cli_commands import cli, handle_exceptions
from core.exceptions import TaskNotFoundError


@pytest.fixture
def runner():
    """Provide a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_config():
    """Provide sample configuration for testing."""
    return {
        "tasks": [
            {
                "name": "test_task",
                "command": "echo test",
                "description": "Test task",
                "last_run": "20240101_120000_000000",
                "last_status": "success",
            },
            {
                "name": "another_task",
                "command": "echo another",
                "description": "Another task",
                "last_run": "",
                "last_status": "no logs",
            },
        ],
        "groups": [
            {
                "name": "test_group",
                "description": "Test group",
                "tasks": ["test_task", "another_task"],
                "execution": "serial",
                "stop_on_error": False,
            }
        ],
        "_task_sources": {"test_task": "tasks/test.yaml"},
        "_group_sources": {"test_group": "groups/test.yaml"},
    }


class TestHandleExceptions:
    """Tests for handle_exceptions decorator."""

    def test_handles_signalbox_error(self, runner):
        """Test that SignalboxError is caught and handled."""

        @handle_exceptions
        def failing_command():
            raise TaskNotFoundError("test_script")

        with pytest.raises(SystemExit) as exc_info:
            failing_command()

        assert exc_info.value.code == 3

    def test_handles_generic_exception(self, runner):
        """Test that generic exceptions are caught."""

        @handle_exceptions
        def failing_command():
            raise ValueError("Something went wrong")

        with pytest.raises(SystemExit) as exc_info:
            failing_command()

        assert exc_info.value.code == 1

    def test_passes_through_successful_execution(self):
        """Test that successful execution passes through."""

        @handle_exceptions
        def successful_command():
            return "success"

        result = successful_command()
        assert result == "success"


class TestInitCommand:
    """Tests for init command."""

    @patch("core.cli_commands.os.path.exists")
    @patch("core.cli_commands.os.makedirs")
    @patch("core.cli_commands.shutil.copytree")
    @patch("builtins.open", new_callable=mock_open)
    def test_init_creates_new_config(self, mock_file, mock_copytree, mock_makedirs, mock_exists, runner):
        """Test init command creates new configuration."""
        # Return False for the config home check (no existing config to backup),
        # True for the template_config check (so the copytree branch is taken).
        mock_exists.side_effect = lambda path: str(path).endswith("core/config") or str(path).endswith("core" + __import__("os").sep + "config")

        result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0
        assert "Signalbox initialized successfully!" in result.output
        assert "Created logs directory" in result.output

    @patch("core.cli_commands.os.path.exists")
    @patch("core.cli_commands.shutil.move")
    @patch("core.cli_commands.shutil.copytree")
    @patch("core.cli_commands.os.makedirs")
    def test_init_with_existing_config_confirms_backup(
        self, mock_makedirs, mock_copytree, mock_move, mock_exists, runner
    ):
        """Test init command handles existing config with confirmation."""
        mock_exists.return_value = True

        # User confirms backup
        result = runner.invoke(cli, ["init"], input="y\n")

        assert result.exit_code == 0
        assert "Backed up existing config" in result.output

    @patch("core.cli_commands.os.path.exists")
    def test_init_with_existing_config_cancels(self, mock_exists, runner):
        """Test init command respects cancellation."""
        mock_exists.return_value = True

        # User cancels
        result = runner.invoke(cli, ["init"], input="n\n")

        assert result.exit_code == 0
        assert "Backed up" not in result.output


class TestListCommand:
    """Tests for list command."""

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.load_runtime_state")
    @patch("core.cli_commands.merge_config_with_runtime_state")
    @patch("core.cli_commands.get_config_value")
    def test_list_displays_scripts(self, mock_get_config, mock_merge, mock_runtime, mock_load, runner, sample_config):
        """Test list command displays all scripts."""
        mock_load.return_value = sample_config
        mock_runtime.return_value = {"tasks": {}, "groups": {}}
        mock_merge.return_value = sample_config
        mock_get_config.return_value = "%Y-%m-%d %H:%M:%S"

        result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "test_task" in result.output
        assert "another_task" in result.output
        assert "success" in result.output
        assert "no logs" in result.output

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.load_runtime_state")
    @patch("core.cli_commands.merge_config_with_runtime_state")
    @patch("core.cli_commands.get_config_value")
    def test_list_handles_timestamp_formatting(
        self, mock_get_config, mock_merge, mock_runtime, mock_load, runner, sample_config
    ):
        """Test list command formats timestamps correctly."""
        mock_load.return_value = sample_config
        mock_runtime.return_value = {"tasks": {}, "groups": {}}
        mock_merge.return_value = sample_config
        mock_get_config.return_value = "%Y-%m-%d"

        result = runner.invoke(cli, ["list"])

        assert result.exit_code == 0
        assert "2024-01-01" in result.output


class TestRunCommand:
    """Tests for run command."""

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_task")
    def test_run_executes_script(self, mock_run_script, mock_load, runner, sample_config):
        """Test run command executes a script."""
        mock_load.return_value = sample_config
        mock_run_script.return_value = True

        result = runner.invoke(cli, ["run", "test_task"])

        assert result.exit_code == 0
        mock_run_script.assert_called_once_with("test_task", sample_config)

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_task")
    def test_run_handles_script_not_found(self, mock_run_script, mock_load, runner, sample_config):
        """Test run command handles script not found error."""
        mock_load.return_value = sample_config
        mock_run_script.side_effect = TaskNotFoundError("nonexistent")

        result = runner.invoke(cli, ["run", "nonexistent"])

        assert result.exit_code == 3
        assert "not found" in result.output


class TestRunAllCommand:
    """Tests for task run --all command."""

    @patch("core.cli_commands.os.listdir", return_value=[])
    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_task")
    def test_run_all_executes_all_scripts(self, mock_run_script, mock_load, mock_listdir, runner, sample_config):
        """Test task run --all executes all scripts."""
        mock_load.return_value = sample_config
        mock_run_script.return_value = True

        result = runner.invoke(cli, ["task", "run", "--all"])

        assert result.exit_code == 0
        assert "Running all tasks" in result.output
        assert mock_run_script.call_count == 2

    @patch("core.cli_commands.os.listdir", return_value=[])
    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_task")
    def test_run_all_continues_on_error(self, mock_run_script, mock_load, mock_listdir, runner, sample_config):
        """Test task run --all continues even if one script fails."""
        mock_load.return_value = sample_config
        mock_run_script.side_effect = [True, TaskNotFoundError("test")]

        result = runner.invoke(cli, ["task", "run", "--all"])

        assert result.exit_code == 1
        assert "task(s) failed" in result.output


class TestRunGroupCommand:
    """Tests for group run command."""

    @patch("core.cli_commands.os.listdir", return_value=[])
    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_group_serial")
    @patch("core.cli_commands.save_group_runtime_state")
    @patch("core.cli_commands.get_config_value")
    def test_run_group_serial_execution(
        self, mock_get_config, mock_save, mock_run_serial, mock_load, mock_listdir, runner, sample_config
    ):
        """Test group run with serial execution."""
        mock_load.return_value = sample_config
        mock_run_serial.return_value = 1
        mock_get_config.return_value = "%Y%m%d_%H%M%S_%f"

        result = runner.invoke(cli, ["group", "run", "test_group"])

        assert result.exit_code == 0
        assert "Running group test_group" in result.output
        assert "serial" in result.output
        assert mock_run_serial.called

    @patch("core.cli_commands.os.listdir", return_value=[])
    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_group_parallel")
    @patch("core.cli_commands.save_group_runtime_state")
    @patch("core.cli_commands.get_config_value")
    def test_run_group_parallel_execution(
        self, mock_get_config, mock_save, mock_run_parallel, mock_load, mock_listdir, runner, sample_config
    ):
        """Test group run with parallel execution."""
        # Modify config for parallel execution
        sample_config["groups"][0]["execution"] = "parallel"
        mock_load.return_value = sample_config
        mock_run_parallel.return_value = 1
        mock_get_config.return_value = "%Y%m%d_%H%M%S_%f"

        result = runner.invoke(cli, ["group", "run", "test_group"])

        assert result.exit_code == 0
        assert "parallel" in result.output
        assert mock_run_parallel.called

    @patch("core.cli_commands.load_config")
    def test_run_group_not_found(self, mock_load, runner, sample_config):
        """Test group run handles group not found error."""
        mock_load.return_value = sample_config

        result = runner.invoke(cli, ["group", "run", "nonexistent_group"])

        assert result.exit_code == 3
        assert "not found" in result.output

    @patch("core.cli_commands.os.listdir", return_value=[])
    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_group_serial")
    @patch("core.cli_commands.load_runtime_state")
    @patch("core.cli_commands.save_group_runtime_state")
    @patch("core.cli_commands.get_config_value")
    def test_run_group_calculates_status(
        self, mock_get_config, mock_save, mock_runtime, mock_run_serial, mock_load, mock_listdir, runner, sample_config
    ):
        """Test group run calculates correct status based on results."""
        mock_load.return_value = sample_config
        mock_get_config.return_value = "%Y%m%d_%H%M%S_%f"

        # All tasks succeed → "success"
        mock_runtime.return_value = {
            "tasks": {"test_task": {"last_status": "success"}, "another_task": {"last_status": "success"}}
        }
        runner.invoke(cli, ["group", "run", "test_group"])
        assert mock_save.call_args[1]["last_status"] == "success"

        # First task succeeds, second fails → "partial"
        mock_runtime.return_value = {
            "tasks": {"test_task": {"last_status": "success"}, "another_task": {"last_status": "failed"}}
        }
        runner.invoke(cli, ["group", "run", "test_group"])
        assert mock_save.call_args[1]["last_status"] == "partial"

        # All tasks fail → "failed"
        mock_runtime.return_value = {
            "tasks": {"test_task": {"last_status": "failed"}, "another_task": {"last_status": "failed"}}
        }
        runner.invoke(cli, ["group", "run", "test_group"])
        assert mock_save.call_args[1]["last_status"] == "failed"


class TestLogsCommand:
    """Tests for log show command."""

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.log_manager.get_latest_log")
    @patch("core.cli_commands.log_manager.read_log_content")
    @patch("core.cli_commands.log_manager.format_log_with_colors")
    @patch("core.cli_commands.get_config_value")
    def test_logs_displays_latest_log(
        self, mock_get_config, mock_format, mock_read, mock_get_log, mock_load, runner, sample_config
    ):
        """Test log show displays latest log."""
        mock_load.return_value = sample_config
        mock_get_log.return_value = ("/path/to/log.txt", True)
        mock_read.return_value = "Log content"
        mock_format.return_value = [("Log content", None)]
        mock_get_config.return_value = False

        result = runner.invoke(cli, ["log", "show", "test_task"])

        assert result.exit_code == 0
        assert "Log content" in result.output

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.log_manager.get_latest_log")
    def test_logs_handles_no_logs(self, mock_get_log, mock_load, runner, sample_config):
        """Test log show handles missing logs."""
        mock_load.return_value = sample_config
        mock_get_log.return_value = (None, False)

        result = runner.invoke(cli, ["log", "show", "test_task"])

        assert result.exit_code == 0
        assert "No logs found" in result.output

    @patch("core.cli_commands.load_config")
    def test_logs_handles_script_not_found(self, mock_load, runner, sample_config):
        """Test log show handles script not found."""
        mock_load.return_value = sample_config

        result = runner.invoke(cli, ["log", "show", "nonexistent"])

        assert result.exit_code == 3


class TestClearLogsCommand:
    """Tests for log clear --task command."""

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.log_manager.clear_task_logs")
    def test_clear_logs_removes_logs(self, mock_clear, mock_load, runner, sample_config):
        """Test log clear --task removes logs for a task."""
        mock_load.return_value = sample_config
        mock_clear.return_value = True

        result = runner.invoke(cli, ["log", "clear", "--task", "test_task"])

        assert result.exit_code == 0
        assert "Cleared logs for test_task" in result.output

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.log_manager.clear_task_logs")
    def test_clear_logs_handles_no_logs(self, mock_clear, mock_load, runner, sample_config):
        """Test log clear --task handles no logs found."""
        mock_load.return_value = sample_config
        mock_clear.return_value = False

        result = runner.invoke(cli, ["log", "clear", "--task", "test_task"])

        assert result.exit_code == 0
        assert "No logs found for test_task" in result.output


class TestClearAllLogsCommand:
    """Tests for log clear --all command."""

    @patch("core.cli_commands.log_manager.clear_all_logs")
    def test_clear_all_logs_removes_all(self, mock_clear, runner):
        """Test log clear --all removes all logs."""
        mock_clear.return_value = True

        result = runner.invoke(cli, ["log", "clear", "--all"])

        assert result.exit_code == 0
        assert "Cleared all logs" in result.output

    @patch("core.cli_commands.log_manager.clear_all_logs")
    def test_clear_all_logs_handles_no_directory(self, mock_clear, runner):
        """Test log clear --all handles missing directory."""
        mock_clear.return_value = False

        result = runner.invoke(cli, ["log", "clear", "--all"])

        assert result.exit_code == 0
        assert "No logs directory found" in result.output


class TestListGroupsCommand:
    """Tests for group list command."""

    @patch("core.cli_commands.load_config")
    def test_list_groups_displays_all_groups(self, mock_load, runner, sample_config):
        """Test group list displays all groups."""
        mock_load.return_value = sample_config

        result = runner.invoke(cli, ["group", "list"])

        assert result.exit_code == 0
        assert "test_group" in result.output

    @patch("core.cli_commands.load_config")
    def test_list_groups_handles_no_groups(self, mock_load, runner):
        """Test group list handles no groups defined."""
        mock_load.return_value = {"tasks": [], "groups": []}

        result = runner.invoke(cli, ["group", "list"])

        assert result.exit_code == 0
        assert "No groups defined" in result.output

    @patch("core.cli_commands.load_config")
    def test_list_groups_shows_scheduled_info(self, mock_load, runner, sample_config):
        """Test group list shows schedule information."""
        sample_config["groups"][0]["schedule"] = "0 2 * * *"
        mock_load.return_value = sample_config

        result = runner.invoke(cli, ["group", "list"])

        assert result.exit_code == 0
        assert "0 2 * * *" in result.output


class TestShowConfigCommand:
    """Tests for config show command."""

    @patch("core.cli_commands.load_global_config")
    def test_show_config_displays_configuration(self, mock_load, runner):
        """Test config show displays global configuration."""
        mock_load.return_value = {
            "execution": {"default_timeout": 300},
            "logging": {"timestamp_format": "%Y%m%d_%H%M%S_%f"},
        }

        result = runner.invoke(cli, ["config", "show"])

        assert result.exit_code == 0
        assert "execution" in result.output
        assert "default_timeout" in result.output

    @patch("core.cli_commands.load_global_config")
    def test_show_config_handles_no_config(self, mock_load, runner):
        """Test config show handles no configuration."""
        mock_load.return_value = {}

        result = runner.invoke(cli, ["config", "show"])

        assert result.exit_code == 0
        assert "No global configuration found" in result.output


class TestGetSettingCommand:
    """Tests for config show <key> command."""

    @patch("core.cli_commands.get_config_value")
    def test_get_setting_retrieves_value(self, mock_get, runner):
        """Test config show <key> retrieves a config value."""
        mock_get.return_value = 300

        result = runner.invoke(cli, ["config", "show", "execution.default_timeout"])

        assert result.exit_code == 0
        assert "300" in result.output

    @patch("core.cli_commands.get_config_value")
    def test_get_setting_handles_not_found(self, mock_get, runner):
        """Test config show <key> handles setting not found."""
        mock_get.return_value = None

        result = runner.invoke(cli, ["config", "show", "nonexistent.setting"])

        assert result.exit_code == 0
        assert "not found" in result.output


class TestListSchedulesCommand:
    """Tests for list-schedules command."""

    @patch("core.cli_commands.load_config")
    def test_list_schedules_displays_scheduled_groups(self, mock_load, runner, sample_config):
        """Test list-schedules displays scheduled groups."""
        sample_config["groups"][0]["schedule"] = "0 2 * * *"
        mock_load.return_value = sample_config

        result = runner.invoke(cli, ["list-schedules"])

        assert result.exit_code == 0
        assert "test_group" in result.output
        assert "0 2 * * *" in result.output

    @patch("core.cli_commands.load_config")
    def test_list_schedules_handles_no_schedules(self, mock_load, runner, sample_config):
        """Test list-schedules handles no scheduled groups."""
        mock_load.return_value = sample_config

        result = runner.invoke(cli, ["list-schedules"])

        assert result.exit_code == 0
        assert "No scheduled groups" in result.output


class TestExportSystemdCommand:
    """Tests for export-systemd command."""

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.exporters.export_systemd")
    @patch("core.cli_commands.exporters.get_systemd_install_instructions")
    def test_export_systemd_generates_files(self, mock_instructions, mock_export, mock_load, runner, sample_config):
        """Test export-systemd generates systemd files."""
        mock_load.return_value = sample_config
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files = ["/tmp/test.service", "/tmp/test.timer"]
        mock_export.return_value = mock_result
        mock_instructions.return_value = ["Install instructions"]

        result = runner.invoke(cli, ["export-systemd", "test_group"])

        assert result.exit_code == 0
        assert "Generated" in result.output

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.exporters.export_systemd")
    def test_export_systemd_handles_error(self, mock_export, mock_load, runner, sample_config):
        """Test export-systemd handles export errors."""
        mock_load.return_value = sample_config
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Export failed"
        mock_export.return_value = mock_result

        result = runner.invoke(cli, ["export-systemd", "test_group"])

        assert result.exit_code == 0
        assert "Error" in result.output


class TestExportCronCommand:
    """Tests for export-cron command."""

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.exporters.export_cron")
    @patch("core.cli_commands.exporters.get_cron_install_instructions")
    def test_export_cron_generates_file(self, mock_instructions, mock_export, mock_load, runner, sample_config):
        """Test export-cron generates cron file."""
        mock_load.return_value = sample_config
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files = ["/tmp/test.cron"]
        mock_result.cron_entry = "0 2 * * * command"
        mock_export.return_value = mock_result
        mock_instructions.return_value = ["Install instructions"]

        result = runner.invoke(cli, ["export-cron", "test_group"])

        assert result.exit_code == 0
        assert "Generated" in result.output


class TestValidateCommand:
    """Tests for validate command."""

    @patch("core.cli_commands.validator.validate_configuration")
    @patch("core.cli_commands.validator.get_validation_summary")
    @patch("core.cli_commands.get_config_value")
    def test_validate_successful(self, mock_get_config, mock_summary, mock_validate, runner):
        """Test validate command with valid configuration."""
        mock_result = MagicMock()
        mock_result.errors = []
        mock_result.warnings = []
        mock_result.has_issues = False
        mock_result.is_valid = True
        mock_result.files_used = ["config.yaml"]
        mock_result.config = {"tasks": [], "groups": []}
        mock_validate.return_value = mock_result
        mock_summary.return_value = {"tasks": 5, "groups": 2, "scheduled_groups": 1}
        mock_get_config.return_value = False

        result = runner.invoke(cli, ["validate"])

        assert result.exit_code == 0
        assert "Configuration is valid" in result.output

    @patch("core.cli_commands.validator.validate_configuration")
    def test_validate_with_errors(self, mock_validate, runner):
        """Test validate command with errors."""
        mock_result = MagicMock()
        mock_result.errors = ["Error 1", "Error 2"]
        mock_result.warnings = []
        mock_result.has_issues = True
        mock_result.is_valid = False
        mock_result.files_used = ["config.yaml"]
        mock_validate.return_value = mock_result

        result = runner.invoke(cli, ["validate"])

        assert result.exit_code == 2
        assert "Errors Found" in result.output

    @patch("core.cli_commands.validator.validate_configuration")
    @patch("core.cli_commands.get_config_value")
    def test_validate_with_warnings_strict_mode(self, mock_get_config, mock_validate, runner):
        """Test validate command with warnings in strict mode."""
        mock_result = MagicMock()
        mock_result.errors = []
        mock_result.warnings = ["Warning 1"]
        mock_result.has_issues = True
        mock_result.is_valid = True
        mock_result.files_used = ["config.yaml"]
        mock_validate.return_value = mock_result
        mock_get_config.return_value = True  # strict mode enabled

        result = runner.invoke(cli, ["validate"])

        assert result.exit_code == 2
        assert "Warnings" in result.output


class TestNotifyTestCommand:
    """Tests for notify-test command."""

    @patch("core.cli_commands.notifications.send_notification")
    @patch("platform.system")
    def test_notify_test_sends_notification(self, mock_system, mock_send, runner):
        """Test notify-test sends a test notification."""
        mock_system.return_value = "Linux"
        mock_send.return_value = True

        result = runner.invoke(cli, ["notify-test"])

        assert result.exit_code == 0
        assert "Notification sent successfully" in result.output

    @patch("core.cli_commands.notifications.send_notification")
    @patch("platform.system")
    def test_notify_test_handles_failure(self, mock_system, mock_send, runner):
        """Test notify-test handles notification failure."""
        mock_system.return_value = "Linux"
        mock_send.return_value = False

        result = runner.invoke(cli, ["notify-test"])

        assert result.exit_code == 1
        assert "Failed to send notification" in result.output

    @patch("core.cli_commands.notifications.send_notification")
    @patch("platform.system")
    def test_notify_test_custom_parameters(self, mock_system, mock_send, runner):
        """Test notify-test with custom title and message."""
        mock_system.return_value = "Darwin"
        mock_send.return_value = True

        result = runner.invoke(cli, ["notify-test", "--title", "Custom Title", "--message", "Custom Message"])

        assert result.exit_code == 0
        assert "Custom Title" in result.output
        assert "Custom Message" in result.output
        mock_send.assert_called_with("Custom Title", "Custom Message", "normal")


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_cli_group_exists(self, runner):
        """Test that CLI group is defined."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "signalbox" in result.output

    def test_all_commands_registered(self, runner):
        """Test that all expected top-level commands and groups are registered."""
        result = runner.invoke(cli, ["--help"])

        commands = [
            "init",
            "list",
            "run",
            "validate",
            "task",
            "group",
            "log",
            "config",
            "list-schedules",
            "export-systemd",
            "export-cron",
            "notify-test",
        ]

        for command in commands:
            assert command in result.output, f"'{command}' not found in CLI help output"
