"""
Tests for core.cli_commands module.

Tests CLI command functionality including list, run, run-group, logs,
validation, and other commands.
"""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, mock_open

from core.cli_commands import (
    cli,
    init,
    list as list_cmd,
    run,
    run_all,
    run_group,
    logs,
    # history,  # Command removed
    clear_logs,
    clear_all_logs,
    list_groups,
    show_config,
    get_setting,
    list_schedules,
    export_systemd,
    export_cron,
    validate,
    notify_test,
    handle_exceptions,
)
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
        mock_exists.return_value = False

        result = runner.invoke(init)

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
        result = runner.invoke(init, input="y\n")

        assert result.exit_code == 0
        assert "Backed up existing config" in result.output

    @patch("core.cli_commands.os.path.exists")
    def test_init_with_existing_config_cancels(self, mock_exists, runner):
        """Test init command respects cancellation."""
        mock_exists.return_value = True

        # User cancels
        result = runner.invoke(init, input="n\n")

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

        result = runner.invoke(list_cmd)

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

        result = runner.invoke(list_cmd)

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

        result = runner.invoke(run, ["test_task"])

        assert result.exit_code == 0
        mock_run_script.assert_called_once_with("test_task", sample_config)

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_task")
    def test_run_handles_script_not_found(self, mock_run_script, mock_load, runner, sample_config):
        """Test run command handles script not found error."""
        mock_load.return_value = sample_config
        mock_run_script.side_effect = TaskNotFoundError("nonexistent")

        result = runner.invoke(run, ["nonexistent"])

        assert result.exit_code == 3
        assert "not found" in result.output


class TestRunAllCommand:
    """Tests for run_all command."""

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_task")
    def test_run_all_executes_all_scripts(self, mock_run_script, mock_load, runner, sample_config):
        """Test run_all executes all scripts."""
        mock_load.return_value = sample_config
        mock_run_script.return_value = True

        result = runner.invoke(run_all)

        assert result.exit_code == 0
        assert "Running all tasks" in result.output
        assert mock_run_script.call_count == 2

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_task")
    def test_run_all_continues_on_error(self, mock_run_script, mock_load, runner, sample_config):
        """Test run_all continues even if one script fails."""
        mock_load.return_value = sample_config
        mock_run_script.side_effect = [True, TaskNotFoundError("test")]

        result = runner.invoke(run_all)

        assert result.exit_code == 0
        assert "All tasks executed" in result.output


class TestRunGroupCommand:
    """Tests for run_group command."""

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_group_serial")
    @patch("core.cli_commands.save_group_runtime_state")
    @patch("core.cli_commands.get_config_value")
    def test_run_group_serial_execution(
        self, mock_get_config, mock_save, mock_run_serial, mock_load, runner, sample_config
    ):
        """Test run_group with serial execution."""
        mock_load.return_value = sample_config
        mock_run_serial.return_value = 2
        mock_get_config.return_value = "%Y%m%d_%H%M%S_%f"

        result = runner.invoke(run_group, ["test_group"])

        assert result.exit_code == 0
        assert "Running group test_group" in result.output
        assert "serial" in result.output
        mock_run_serial.assert_called_once()

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_group_parallel")
    @patch("core.cli_commands.save_group_runtime_state")
    @patch("core.cli_commands.get_config_value")
    def test_run_group_parallel_execution(
        self, mock_get_config, mock_save, mock_run_parallel, mock_load, runner, sample_config
    ):
        """Test run_group with parallel execution."""
        # Modify config for parallel execution
        sample_config["groups"][0]["execution"] = "parallel"
        mock_load.return_value = sample_config
        mock_run_parallel.return_value = 2
        mock_get_config.return_value = "%Y%m%d_%H%M%S_%f"

        result = runner.invoke(run_group, ["test_group"])

        assert result.exit_code == 0
        assert "parallel" in result.output
        mock_run_parallel.assert_called_once()

    @patch("core.cli_commands.load_config")
    def test_run_group_not_found(self, mock_load, runner, sample_config):
        """Test run_group handles group not found error."""
        mock_load.return_value = sample_config

        result = runner.invoke(run_group, ["nonexistent_group"])

        assert result.exit_code == 3
        assert "not found" in result.output

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.run_group_serial")
    @patch("core.cli_commands.save_group_runtime_state")
    @patch("core.cli_commands.get_config_value")
    def test_run_group_calculates_status(
        self, mock_get_config, mock_save, mock_run_serial, mock_load, runner, sample_config
    ):
        """Test run_group calculates correct status based on results."""
        mock_load.return_value = sample_config
        mock_get_config.return_value = "%Y%m%d_%H%M%S_%f"

        # Test different scenarios
        scenarios = [
            (2, "success"),  # All succeeded
            (1, "partial"),  # Some succeeded
            (0, "failed"),  # None succeeded
        ]

        for tasks_successful, expected_status in scenarios:
            mock_run_serial.return_value = tasks_successful
            runner.invoke(run_group, ["test_group"])

            # Verify save_group_runtime_state was called with correct status
            call_args = mock_save.call_args
            assert call_args[1]["last_status"] == expected_status


class TestLogsCommand:
    """Tests for logs command."""

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.log_manager.get_latest_log")
    @patch("core.cli_commands.log_manager.read_log_content")
    @patch("core.cli_commands.log_manager.format_log_with_colors")
    @patch("core.cli_commands.get_config_value")
    def test_logs_displays_latest_log(
        self, mock_get_config, mock_format, mock_read, mock_get_log, mock_load, runner, sample_config
    ):
        """Test logs command displays latest log."""
        mock_load.return_value = sample_config
        mock_get_log.return_value = ("/path/to/log.txt", True)
        mock_read.return_value = "Log content"
        mock_format.return_value = [("Log content", None)]
        mock_get_config.return_value = False

        result = runner.invoke(logs, ["test_task"])

        assert result.exit_code == 0
        assert "Log content" in result.output

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.log_manager.get_latest_log")
    def test_logs_handles_no_logs(self, mock_get_log, mock_load, runner, sample_config):
        """Test logs command handles missing logs."""
        mock_load.return_value = sample_config
        mock_get_log.return_value = (None, False)

        result = runner.invoke(logs, ["test_task"])

        assert result.exit_code == 0
        assert "No logs found" in result.output

    @patch("core.cli_commands.load_config")
    def test_logs_handles_script_not_found(self, mock_load, runner, sample_config):
        """Test logs command handles script not found."""
        mock_load.return_value = sample_config

        result = runner.invoke(logs, ["nonexistent"])

        assert result.exit_code == 3


# class TestHistoryCommand:
#     """Tests for history command."""
# 
#     @patch("core.cli_commands.load_config")
#     @patch("core.cli_commands.log_manager.get_log_history")
#     @patch("core.cli_commands.log_manager.get_script_log_dir")
#     @patch("core.cli_commands.get_config_value")
#     def test_history_displays_log_files(
#         self, mock_get_config, mock_get_dir, mock_get_history, mock_load, runner, sample_config
#     ):
#         """Test history command displays log history."""
#         mock_load.return_value = sample_config
#         mock_get_history.return_value = ([("log1.txt", 1704110400), ("log2.txt", 1704196800)], True)
#         mock_get_dir.return_value = "/logs/test_script"
#         mock_get_config.side_effect = lambda key, default: {
#             "display.include_paths": False,
#             "display.date_format": "%Y-%m-%d",
#         }.get(key, default)
# 
#         result = runner.invoke(history, ["test_script"])
# 
#         assert result.exit_code == 0
#         assert "History for test_script" in result.output
#         assert "log1.txt" in result.output
#         assert "log2.txt" in result.output
# 
#     @patch("core.cli_commands.load_config")
#     @patch("core.cli_commands.log_manager.get_log_history")
#     def test_history_handles_no_history(self, mock_get_history, mock_load, runner, sample_config):
#         """Test history command handles no history."""
#         mock_load.return_value = sample_config
#         mock_get_history.return_value = ([], False)
# 
#         result = runner.invoke(history, ["test_script"])
# 
#         assert result.exit_code == 0
#         assert "No history found" in result.output


class TestClearLogsCommand:
    """Tests for clear_logs command."""

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.log_manager.clear_task_logs")
    def test_clear_logs_removes_logs(self, mock_clear, mock_load, runner, sample_config):
        """Test clear_logs removes logs for a task."""
        mock_load.return_value = sample_config
        mock_clear.return_value = True

        result = runner.invoke(clear_logs, ["test_task"])

        assert result.exit_code == 0
        assert "Cleared logs for test_task" in result.output

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.log_manager.clear_task_logs")
    def test_clear_logs_handles_no_logs(self, mock_clear, mock_load, runner, sample_config):
        """Test clear_logs handles no logs found."""
        mock_load.return_value = sample_config
        mock_clear.return_value = False

        result = runner.invoke(clear_logs, ["test_task"])

        assert result.exit_code == 0
        assert "No logs found for test_task" in result.output


class TestClearAllLogsCommand:
    """Tests for clear_all_logs command."""

    @patch("core.cli_commands.log_manager.clear_all_logs")
    def test_clear_all_logs_removes_all(self, mock_clear, runner):
        """Test clear_all_logs removes all logs."""
        mock_clear.return_value = True

        result = runner.invoke(clear_all_logs)

        assert result.exit_code == 0
        assert "Cleared all logs" in result.output

    @patch("core.cli_commands.log_manager.clear_all_logs")
    def test_clear_all_logs_handles_no_directory(self, mock_clear, runner):
        """Test clear_all_logs handles missing directory."""
        mock_clear.return_value = False

        result = runner.invoke(clear_all_logs)

        assert result.exit_code == 0
        assert "No logs directory found" in result.output


class TestListGroupsCommand:
    """Tests for list_groups command."""

    @patch("core.cli_commands.load_config")
    def test_list_groups_displays_all_groups(self, mock_load, runner, sample_config):
        """Test list_groups displays all groups."""
        mock_load.return_value = sample_config

        result = runner.invoke(list_groups)

        assert result.exit_code == 0
        assert "Group: test_group" in result.output
        assert "test_task" in result.output
        assert "another_task" in result.output

    @patch("core.cli_commands.load_config")
    def test_list_groups_handles_no_groups(self, mock_load, runner):
        """Test list_groups handles no groups defined."""
        mock_load.return_value = {"tasks": [], "groups": []}

        result = runner.invoke(list_groups)

        assert result.exit_code == 0
        assert "No groups defined" in result.output

    @patch("core.cli_commands.load_config")
    def test_list_groups_shows_scheduled_info(self, mock_load, runner, sample_config):
        """Test list_groups shows schedule information."""
        sample_config["groups"][0]["schedule"] = "0 2 * * *"
        mock_load.return_value = sample_config

        result = runner.invoke(list_groups)

        assert result.exit_code == 0
        assert "scheduled: 0 2 * * *" in result.output


class TestShowConfigCommand:
    """Tests for show_config command."""

    @patch("core.cli_commands.load_global_config")
    def test_show_config_displays_configuration(self, mock_load, runner):
        """Test show_config displays global configuration."""
        mock_load.return_value = {
            "execution": {"default_timeout": 300},
            "logging": {"timestamp_format": "%Y%m%d_%H%M%S_%f"},
        }

        result = runner.invoke(show_config)

        assert result.exit_code == 0
        assert "execution" in result.output
        assert "default_timeout" in result.output

    @patch("core.cli_commands.load_global_config")
    def test_show_config_handles_no_config(self, mock_load, runner):
        """Test show_config handles no configuration."""
        mock_load.return_value = {}

        result = runner.invoke(show_config)

        assert result.exit_code == 0
        assert "No global configuration found" in result.output


class TestGetSettingCommand:
    """Tests for get_setting command."""

    @patch("core.cli_commands.get_config_value")
    def test_get_setting_retrieves_value(self, mock_get, runner):
        """Test get_setting retrieves a config value."""
        mock_get.return_value = 300

        result = runner.invoke(get_setting, ["execution.default_timeout"])

        assert result.exit_code == 0
        assert "300" in result.output

    @patch("core.cli_commands.get_config_value")
    def test_get_setting_handles_not_found(self, mock_get, runner):
        """Test get_setting handles setting not found."""
        mock_get.return_value = None

        result = runner.invoke(get_setting, ["nonexistent.setting"])

        assert result.exit_code == 0
        assert "not found" in result.output


class TestListSchedulesCommand:
    """Tests for list_schedules command."""

    @patch("core.cli_commands.load_config")
    def test_list_schedules_displays_scheduled_groups(self, mock_load, runner, sample_config):
        """Test list_schedules displays scheduled groups."""
        sample_config["groups"][0]["schedule"] = "0 2 * * *"
        mock_load.return_value = sample_config

        result = runner.invoke(list_schedules)

        assert result.exit_code == 0
        assert "Scheduled Groups" in result.output
        assert "test_group" in result.output
        assert "0 2 * * *" in result.output

    @patch("core.cli_commands.load_config")
    def test_list_schedules_handles_no_schedules(self, mock_load, runner, sample_config):
        """Test list_schedules handles no scheduled groups."""
        mock_load.return_value = sample_config

        result = runner.invoke(list_schedules)

        assert result.exit_code == 0
        assert "No scheduled groups" in result.output


class TestExportSystemdCommand:
    """Tests for export_systemd command."""

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.exporters.export_systemd")
    @patch("core.cli_commands.exporters.get_systemd_install_instructions")
    def test_export_systemd_generates_files(self, mock_instructions, mock_export, mock_load, runner, sample_config):
        """Test export_systemd generates systemd files."""
        mock_load.return_value = sample_config
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files = ["/tmp/test.service", "/tmp/test.timer"]
        mock_export.return_value = mock_result
        mock_instructions.return_value = ["Install instructions"]

        result = runner.invoke(export_systemd, ["test_group"])

        assert result.exit_code == 0
        assert "Generated" in result.output

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.exporters.export_systemd")
    def test_export_systemd_handles_error(self, mock_export, mock_load, runner, sample_config):
        """Test export_systemd handles export errors."""
        mock_load.return_value = sample_config
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Export failed"
        mock_export.return_value = mock_result

        result = runner.invoke(export_systemd, ["test_group"])

        assert result.exit_code == 0
        assert "Error" in result.output


class TestExportCronCommand:
    """Tests for export_cron command."""

    @patch("core.cli_commands.load_config")
    @patch("core.cli_commands.exporters.export_cron")
    @patch("core.cli_commands.exporters.get_cron_install_instructions")
    def test_export_cron_generates_file(self, mock_instructions, mock_export, mock_load, runner, sample_config):
        """Test export_cron generates cron file."""
        mock_load.return_value = sample_config
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.files = ["/tmp/test.cron"]
        mock_result.cron_entry = "0 2 * * * command"
        mock_export.return_value = mock_result
        mock_instructions.return_value = ["Install instructions"]

        result = runner.invoke(export_cron, ["test_group"])

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

        result = runner.invoke(validate)

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

        result = runner.invoke(validate)

        assert result.exit_code == 5
        assert "Errors found" in result.output

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

        result = runner.invoke(validate)

        assert result.exit_code == 5
        assert "Warnings" in result.output


class TestNotifyTestCommand:
    """Tests for notify_test command."""

    @patch("core.cli_commands.notifications.send_notification")
    @patch("platform.system")
    def test_notify_test_sends_notification(self, mock_system, mock_send, runner):
        """Test notify_test sends a test notification."""
        mock_system.return_value = "Linux"
        mock_send.return_value = True

        result = runner.invoke(notify_test)

        assert result.exit_code == 0
        assert "Notification sent successfully" in result.output

    @patch("core.cli_commands.notifications.send_notification")
    @patch("platform.system")
    def test_notify_test_handles_failure(self, mock_system, mock_send, runner):
        """Test notify_test handles notification failure."""
        mock_system.return_value = "Linux"
        mock_send.return_value = False

        result = runner.invoke(notify_test)

        assert result.exit_code == 1
        assert "Failed to send notification" in result.output

    @patch("core.cli_commands.notifications.send_notification")
    @patch("platform.system")
    def test_notify_test_custom_parameters(self, mock_system, mock_send, runner):
        """Test notify_test with custom title and message."""
        mock_system.return_value = "Darwin"
        mock_send.return_value = True

        result = runner.invoke(notify_test, ["--title", "Custom Title", "--message", "Custom Message"])

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
        """Test that all commands are registered."""
        result = runner.invoke(cli, ["--help"])

        commands = [
            "init",
            "list",
            "run",
            "run-all",
            "run-group",
            "logs",
            # "history",  # Command removed
            "clear-logs",
            "clear-all-logs",
            "list-groups",
            "show-config",
            "get-setting",
            "list-schedules",
            "export-systemd",
            "export-cron",
            "validate",
            "notify-test",
        ]

        for command in commands:
            assert command in result.output
