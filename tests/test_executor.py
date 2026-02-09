"""
Tests for core.executor module.

Tests script execution, timeout handling, parallel/serial group execution,
logging, and error handling.
"""

import pytest
from unittest.mock import Mock, patch
import subprocess

from core.executor import run_task, run_group_parallel, run_group_serial
from core.exceptions import ScriptNotFoundError, ExecutionError, ExecutionTimeoutError


class TestRunTask:
    """Tests for run_task function."""

    @patch("core.config.load_config")
    @patch("core.executor.get_config_value")
    @patch("core.executor.get_log_path")
    @patch("core.executor.ensure_log_dir")
    @patch("core.executor.save_script_runtime_state")
    @patch("core.executor.rotate_logs")
    @patch("core.executor.write_execution_log")
    @patch("core.executor.subprocess.run")
    def test_run_task_success(
        self,
        mock_subprocess,
        mock_write_log,
        mock_rotate,
        mock_save_state,
        mock_ensure_dir,
        mock_log_path,
        mock_get_config,
        mock_load_config,
    ):
        """Test successful script execution."""
        # Setup mocks
        mock_get_config.side_effect = lambda key, default: {
            "logging.timestamp_format": "%Y%m%d_%H%M%S_%f",
            "execution.default_timeout": 300,
        }.get(key, default)
        mock_log_path.return_value = "/logs/test_20240101_120000_000000.log"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success output"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        config = {
            "tasks": [{"name": "test_task", "command": "echo 'hello'", "description": "Test"}],
            "_task_sources": {"test_task": "tasks/test.yaml"},
        }
        mock_load_config.side_effect = lambda *args, **kwargs: config

        # Execute
        result = run_task("test_task", config)

        # Verify
        assert result is True
        mock_ensure_dir.assert_called_once_with("test_task")
        mock_subprocess.assert_called_once_with("echo 'hello'", shell=True, capture_output=True, text=True, timeout=300)
        mock_write_log.assert_called_once()
        mock_rotate.assert_called_once()
        mock_save_state.assert_called_once()

        # Verify task was updated
        assert config["tasks"][0]["last_status"] == "success"
        assert "last_run" in config["tasks"][0]

    @patch("core.config.load_config")
    @patch("core.executor.get_config_value")
    @patch("core.executor.get_log_path")
    @patch("core.executor.ensure_log_dir")
    @patch("core.executor.save_script_runtime_state")
    @patch("core.executor.rotate_logs")
    @patch("core.executor.write_execution_log")
    @patch("core.executor.subprocess.run")
    def test_run_task_failure(
        self,
        mock_subprocess,
        mock_write_log,
        mock_rotate,
        mock_save_state,
        mock_ensure_dir,
        mock_log_path,
        mock_get_config,
        mock_load_config,
    ):
        """Test script execution that fails (non-zero exit code)."""
        mock_get_config.side_effect = lambda key, default: {
            "logging.timestamp_format": "%Y%m%d_%H%M%S_%f",
            "execution.default_timeout": 300,
        }.get(key, default)
        mock_log_path.return_value = "/logs/test_fail.log"

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "Some output"
        mock_result.stderr = "Error occurred"
        mock_subprocess.return_value = mock_result

        config = {
            "tasks": [{"name": "failing_task", "command": "exit 1", "description": "Fails"}],
            "_task_sources": {"failing_task": "tasks/fail.yaml"},
        }
        mock_load_config.side_effect = lambda *args, **kwargs: config

        # Execute
        result = run_task("failing_task", config)

        # Verify
        assert result is False
        assert config["tasks"][0]["last_status"] == "failed"
        mock_write_log.assert_called_once()

    def test_run_task_not_found(self):
        """Test running a script that doesn't exist."""
        config = {
            "tasks": [{"name": "existing_task", "command": "echo test", "description": "Test"}],
            "_task_sources": {},
        }

        with pytest.raises(ScriptNotFoundError) as exc_info:
            run_task("nonexistent_task", config)

        assert "nonexistent_task" in str(exc_info.value)

    @patch("core.config.load_config")
    @patch("core.executor.get_config_value")
    @patch("core.executor.get_log_path")
    @patch("core.executor.ensure_log_dir")
    @patch("core.executor.subprocess.run")
    def test_run_task_timeout(self, mock_subprocess, mock_ensure_dir, mock_log_path, mock_get_config, mock_load_config):
        """Test script execution that times out."""
        mock_get_config.side_effect = lambda key, default: {
            "logging.timestamp_format": "%Y%m%d_%H%M%S_%f",
            "execution.default_timeout": 5,
        }.get(key, default)
        mock_log_path.return_value = "/logs/timeout.log"

        # Simulate timeout
        mock_subprocess.side_effect = subprocess.TimeoutExpired("cmd", 5)

        config = {
            "tasks": [{"name": "slow_task", "command": "sleep 100", "description": "Slow"}],
            "_task_sources": {"slow_task": "tasks/slow.yaml"},
        }
        mock_load_config.side_effect = lambda *args, **kwargs: config
        with pytest.raises(ExecutionTimeoutError) as exc_info:
            run_task("slow_task", config)

        assert "slow_task" in str(exc_info.value)
        assert "5" in str(exc_info.value)

    @patch("core.config.load_config")
    @patch("core.executor.get_config_value")
    @patch("core.executor.get_log_path")
    @patch("core.executor.ensure_log_dir")
    @patch("core.executor.rotate_logs")
    @patch("core.executor.write_execution_log")
    @patch("core.executor.subprocess.run")
    def test_run_task_no_timeout(
        self, mock_subprocess, mock_write_log, mock_rotate, mock_ensure_dir, mock_log_path, mock_get_config, mock_load_config
    ):
        """Test script execution with timeout disabled (0 = None)."""
        mock_get_config.side_effect = lambda key, default: {
            "logging.timestamp_format": "%Y%m%d_%H%M%S_%f",
            "execution.default_timeout": 0,
        }.get(key, default)
        mock_log_path.return_value = "/logs/no_timeout.log"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Done"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        config = {
            "tasks": [{"name": "unlimited", "command": "echo test", "description": "Test"}],
            "_task_sources": {},
        }
        mock_load_config.side_effect = lambda *args, **kwargs: config
        run_task("unlimited", config)

        # Verify timeout=None was passed
        call_args = mock_subprocess.call_args
        assert call_args[1]["timeout"] is None

    @patch("core.config.load_config")
    @patch("core.executor.get_config_value")
    @patch("core.executor.get_log_path")
    @patch("core.executor.ensure_log_dir")
    @patch("core.executor.rotate_logs")
    @patch("core.executor.write_execution_log")
    @patch("core.executor.subprocess.run")
    def test_run_task_no_source_tracking(
        self, mock_subprocess, mock_write_log, mock_rotate, mock_ensure_dir, mock_log_path, mock_get_config, mock_load_config
    ):
        """Test script execution when source file is not tracked."""
        mock_get_config.side_effect = lambda key, default: {
            "logging.timestamp_format": "%Y%m%d_%H%M%S_%f",
            "execution.default_timeout": 300,
        }.get(key, default)
        mock_log_path.return_value = "/logs/test.log"

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Output"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        # No _task_sources for this script
        config = {
            "tasks": [{"name": "no_source", "command": "echo test", "description": "Test"}],
            "_task_sources": {},
        }
        mock_load_config.side_effect = lambda *args, **kwargs: config
        result = run_task("no_source", config)

        # Should still succeed
        assert result is True
        assert config["tasks"][0]["last_status"] == "success"

    @patch("core.executor.subprocess.run")
    @patch("core.executor.ensure_log_dir")
    @patch("core.executor.get_log_path")
    @patch("core.executor.get_config_value")
    @patch("core.config.load_config")
    def test_run_task_subprocess_exception(self, mock_load_config, mock_get_config, mock_log_path, mock_ensure_dir, mock_subprocess):
        """Test script execution when subprocess raises an unexpected exception."""
        mock_get_config.side_effect = lambda key, default: {
            "logging.timestamp_format": "%Y%m%d_%H%M%S_%f",
            "execution.default_timeout": 300,
        }.get(key, default)
        mock_log_path.return_value = "/logs/error.log"

        # Simulate unexpected error
        mock_subprocess.side_effect = OSError("Command not found")

        config = {
            "tasks": [{"name": "error_script", "command": "invalid_command", "description": "Error"}],
            "_task_sources": {},
        }
        mock_load_config.return_value = config
        with pytest.raises(ExecutionError) as exc_info:
            run_task("error_script", config)

        assert "error_script" in str(exc_info.value)


class TestRunGroupParallel:
    """Tests for run_group_parallel function."""

    @patch("core.executor.run_task")
    @patch("core.executor.notifications.notify_execution_result")
    @patch("core.executor.get_config_value")
    def test_parallel_all_success(self, mock_get_config, mock_notify, mock_run_task):
        """Test parallel execution where all scripts succeed."""
        mock_get_config.return_value = 5  # max_parallel_workers
        mock_run_task.return_value = True

        config = {"tasks": [], "_task_sources": {}}
        script_names = ["script1", "script2", "script3"]

        success_count = run_group_parallel(script_names, config)

        assert success_count == 3
        assert mock_run_task.call_count == 3
        mock_notify.assert_called_once()

        # Verify notification was called with correct args
        notify_call = mock_notify.call_args
        assert notify_call[1]["total"] == 3
        assert notify_call[1]["passed"] == 3
        assert notify_call[1]["failed"] == 0

    @patch("core.executor.run_task")
    @patch("core.executor.notifications.notify_execution_result")
    @patch("core.executor.get_config_value")
    def test_parallel_some_failures(self, mock_get_config, mock_notify, mock_run_task):
        """Test parallel execution with some failures."""
        mock_get_config.return_value = 5

        # Make script2 fail
        def run_task_side_effect(name, config):
            return name != "script2"

        mock_run_task.side_effect = run_task_side_effect

        config = {"tasks": [], "_task_sources": {}}
        script_names = ["script1", "script2", "script3"]

        success_count = run_group_parallel(script_names, config)

        assert success_count == 2

        notify_call = mock_notify.call_args
        assert notify_call[1]["total"] == 3
        assert notify_call[1]["passed"] == 2
        assert notify_call[1]["failed"] == 1
        assert "script2" in notify_call[1]["failed_names"]

    @patch("core.executor.run_task")
    @patch("core.executor.notifications.notify_execution_result")
    @patch("core.executor.get_config_value")
    def test_parallel_with_exceptions(self, mock_get_config, mock_notify, mock_run_task):
        """Test parallel execution when some scripts raise exceptions."""
        mock_get_config.return_value = 5

        # script1 succeeds, script2 raises exception, script3 succeeds
        def run_task_side_effect(name, config):
            if name == "script2":
                raise ScriptNotFoundError("script2")
            return True

        mock_run_task.side_effect = run_task_side_effect

        config = {"tasks": [], "_task_sources": {}}
        script_names = ["script1", "script2", "script3"]

        success_count = run_group_parallel(script_names, config)

        assert success_count == 2

        notify_call = mock_notify.call_args
        assert notify_call[1]["failed"] == 1
        assert "script2" in notify_call[1]["failed_names"]

    @patch("core.executor.run_task")
    @patch("core.executor.notifications.notify_execution_result")
    @patch("core.executor.get_config_value")
    def test_parallel_respects_max_workers(self, mock_get_config, mock_notify, mock_run_task):
        """Test that max_parallel_workers setting is respected."""
        mock_get_config.return_value = 2  # Limit to 2 workers
        mock_run_task.return_value = True

        config = {"tasks": [], "_task_sources": {}}
        script_names = ["s1", "s2", "s3", "s4", "s5"]

        success_count = run_group_parallel(script_names, config)

        assert success_count == 5
        assert mock_get_config.called


class TestRunGroupSerial:
    """Tests for run_group_serial function."""

    @patch("core.executor.run_task")
    @patch("core.executor.notifications.notify_execution_result")
    def test_serial_all_success(self, mock_notify, mock_run_task):
        """Test serial execution where all scripts succeed."""
        mock_run_task.return_value = True

        config = {"tasks": [], "_task_sources": {}}
        script_names = ["script1", "script2", "script3"]

        success_count = run_group_serial(script_names, config, stop_on_error=False)

        assert success_count == 3
        assert mock_run_task.call_count == 3

        # Verify execution order
        calls = mock_run_task.call_args_list
        assert calls[0][0][0] == "script1"
        assert calls[1][0][0] == "script2"
        assert calls[2][0][0] == "script3"

    @patch("core.executor.run_task")
    @patch("core.executor.notifications.notify_execution_result")
    def test_serial_some_failures_no_stop(self, mock_notify, mock_run_task):
        """Test serial execution with failures but stop_on_error=False."""
        # script2 fails
        mock_run_task.side_effect = [True, False, True]

        config = {"tasks": [], "_task_sources": {}}
        script_names = ["script1", "script2", "script3"]

        success_count = run_group_serial(script_names, config, stop_on_error=False)

        assert success_count == 2
        assert mock_run_task.call_count == 3  # All 3 should run

        notify_call = mock_notify.call_args
        assert notify_call[1]["passed"] == 2
        assert notify_call[1]["failed"] == 1

    @patch("core.executor.run_task")
    @patch("core.executor.notifications.notify_execution_result")
    def test_serial_stop_on_error(self, mock_notify, mock_run_task):
        """Test serial execution with stop_on_error=True."""
        # script2 fails
        mock_run_task.side_effect = [True, False, True]

        config = {"tasks": [], "_task_sources": {}}
        script_names = ["script1", "script2", "script3"]

        success_count = run_group_serial(script_names, config, stop_on_error=True)

        assert success_count == 1
        assert mock_run_task.call_count == 2  # Should stop after script2

        notify_call = mock_notify.call_args
        assert notify_call[1]["passed"] == 1
        assert notify_call[1]["failed"] == 1

    @patch("core.executor.run_task")
    @patch("core.executor.notifications.notify_execution_result")
    def test_serial_exception_no_stop(self, mock_notify, mock_run_task):
        """Test serial execution when script raises exception, stop_on_error=False."""

        def run_task_side_effect(name, config):
            if name == "script2":
                raise ScriptNotFoundError("script2")
            return True

        mock_run_task.side_effect = run_task_side_effect

        config = {"tasks": [], "_task_sources": {}}
        script_names = ["script1", "script2", "script3"]

        success_count = run_group_serial(script_names, config, stop_on_error=False)

        assert success_count == 2
        assert mock_run_task.call_count == 3  # All 3 attempted

    @patch("core.executor.run_task")
    @patch("core.executor.notifications.notify_execution_result")
    def test_serial_exception_stop_on_error(self, mock_notify, mock_run_task):
        """Test serial execution when script raises exception, stop_on_error=True."""

        def run_task_side_effect(name, config):
            if name == "script2":
                raise ExecutionError("script2", "Failed to execute")
            return True

        mock_run_task.side_effect = run_task_side_effect

        config = {"tasks": [], "_task_sources": {}}
        script_names = ["script1", "script2", "script3"]

        success_count = run_group_serial(script_names, config, stop_on_error=True)

        assert success_count == 1
        assert mock_run_task.call_count == 2  # Stops at script2

    @patch("core.executor.run_task")
    @patch("core.executor.notifications.notify_execution_result")
    def test_serial_all_failures(self, mock_notify, mock_run_task):
        """Test serial execution where all scripts fail."""
        mock_run_task.return_value = False

        config = {"tasks": [], "_task_sources": {}}
        script_names = ["script1", "script2", "script3"]

        success_count = run_group_serial(script_names, config, stop_on_error=False)

        assert success_count == 0

        notify_call = mock_notify.call_args
        assert notify_call[1]["passed"] == 0
        assert notify_call[1]["failed"] == 3
        assert len(notify_call[1]["failed_names"]) == 3


class TestExecutorIntegration:
    """Integration tests for executor module."""

    @patch("core.executor.subprocess.run")
    @patch("core.executor.write_execution_log")
    @patch("core.executor.rotate_logs")
    @patch("core.executor.save_script_runtime_state")
    @patch("core.executor.ensure_log_dir")
    @patch("core.executor.get_log_path")
    @patch("core.executor.notifications.notify_execution_result")
    @patch("core.executor.get_config_value")
    @patch("core.config.load_config")
    def test_full_parallel_workflow(
        self,
        mock_load_config,
        mock_get_config,
        mock_notify,
        mock_log_path,
        mock_ensure_dir,
        mock_save_state,
        mock_rotate,
        mock_write_log,
        mock_subprocess,
    ):
        """Test complete parallel execution workflow."""
        def get_config_side_effect(key, default=None):
            if key == "execution.max_parallel_workers":
                return 5
            if key == "logging.timestamp_format":
                return "%Y%m%d_%H%M%S_%f"
            if key == "execution.default_timeout":
                return 300
            return default
        mock_get_config.side_effect = get_config_side_effect
        mock_notify.side_effect = lambda *args, **kwargs: None
        def log_path_side_effect(name, *args, **kwargs):
            if name == "execution.max_parallel_workers":
                return None
            return f"/logs/{name}.log"
        mock_log_path.side_effect = log_path_side_effect

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Output"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        config = {
            "tasks": [
                {"name": "script1", "command": "echo 1", "description": "Test 1"},
                {"name": "script2", "command": "echo 2", "description": "Test 2"},
            ],
            "_task_sources": {"script1": "scripts/test1.yaml", "script2": "scripts/test2.yaml"},
        }
        mock_load_config.side_effect = lambda *args, **kwargs: config
        mock_notify.side_effect = lambda *args, **kwargs: None
        success_count = run_group_parallel(["script1", "script2"], config)

        assert success_count == 2
        assert mock_subprocess.call_count == 2
        mock_notify.assert_called_once()

    @patch("core.executor.subprocess.run")
    @patch("core.executor.write_execution_log")
    @patch("core.executor.rotate_logs")
    @patch("core.executor.save_script_runtime_state")
    @patch("core.executor.ensure_log_dir")
    @patch("core.executor.get_log_path")
    @patch("core.executor.notifications.notify_execution_result")
    @patch("core.executor.get_config_value")
    @patch("core.config.load_config")
    def test_full_serial_workflow(
        self,
        mock_load_config,
        mock_get_config,
        mock_notify,
        mock_log_path,
        mock_ensure_dir,
        mock_save_state,
        mock_rotate,
        mock_write_log,
        mock_subprocess,
    ):
        """Test complete serial execution workflow."""
        def get_config_side_effect(key, default=None):
            if key == "logging.timestamp_format":
                return "%Y%m%d_%H%M%S_%f"
            if key == "execution.default_timeout":
                return 300
            return default
        mock_get_config.side_effect = get_config_side_effect
        mock_notify.side_effect = lambda *args, **kwargs: None
        def log_path_side_effect(name, *args, **kwargs):
            if name == "execution.max_parallel_workers":
                return None
            return f"/logs/{name}.log"
        mock_log_path.side_effect = log_path_side_effect

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Output"
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        config = {
            "tasks": [
                {"name": "script1", "command": "echo 1", "description": "Test 1"},
                {"name": "script2", "command": "echo 2", "description": "Test 2"},
            ],
            "_task_sources": {"script1": "scripts/test1.yaml", "script2": "scripts/test2.yaml"},
        }
        mock_load_config.side_effect = lambda *args, **kwargs: config
        mock_notify.side_effect = lambda *args, **kwargs: None
        success_count = run_group_serial(["script1", "script2"], config, stop_on_error=False)

        assert success_count == 2

        # Verify serial execution (second call happens after first completes)
        assert mock_subprocess.call_count == 2
        calls = mock_subprocess.call_args_list
        assert calls[0][0][0] == "echo 1"
        assert calls[1][0][0] == "echo 2"
