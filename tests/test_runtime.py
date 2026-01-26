"""
Tests for core.runtime module.

Tests runtime state loading, saving, and merging with configuration.
"""

import yaml
from pathlib import Path
from unittest.mock import patch, mock_open

from core.runtime import (
    load_runtime_state,
    save_script_runtime_state,
    save_group_runtime_state,
    merge_config_with_runtime_state,
)


class TestLoadRuntimeState:
    """Tests for load_runtime_state function."""

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.listdir")
    def test_load_empty_runtime_state(self, mock_listdir, mock_exists, mock_resolve):
        """Test loading runtime state when directories don't exist."""
        mock_resolve.side_effect = lambda path: f"/config/{path}"
        mock_exists.return_value = False

        result = load_runtime_state()

        assert result == {"scripts": {}, "groups": {}}

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.listdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_load_script_runtime_state(self, mock_file, mock_listdir, mock_exists, mock_resolve):
        """Test loading runtime state for scripts."""
        mock_resolve.side_effect = lambda path: f"/config/{path}"

        def exists_side_effect(path):
            return path == "/config/runtime/scripts"

        mock_exists.side_effect = exists_side_effect
        mock_listdir.return_value = ["runtime_test.yaml"]

        runtime_data = {"scripts": {"test_script": {"last_run": "20240101_120000", "last_status": "success"}}}
        mock_file.return_value.read.return_value = yaml.dump(runtime_data)

        with patch("yaml.safe_load", return_value=runtime_data):
            result = load_runtime_state()

        assert "test_script" in result["scripts"]
        assert result["scripts"]["test_script"]["last_run"] == "20240101_120000"
        assert result["scripts"]["test_script"]["last_status"] == "success"

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.listdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_load_group_runtime_state(self, mock_file, mock_listdir, mock_exists, mock_resolve):
        """Test loading runtime state for groups."""
        mock_resolve.side_effect = lambda path: f"/config/{path}"

        def exists_side_effect(path):
            return path == "/config/runtime/groups"

        mock_exists.side_effect = exists_side_effect
        mock_listdir.return_value = ["runtime_test_group.yaml"]

        runtime_data = {
            "groups": {
                "test_group": {
                    "last_run": "20240101_120000",
                    "last_status": "success",
                    "execution_count": 5,
                    "scripts_total": 3,
                    "scripts_successful": 3,
                    "success_rate": 100.0,
                }
            }
        }

        with patch("yaml.safe_load", return_value=runtime_data):
            result = load_runtime_state()

        assert "test_group" in result["groups"]
        assert result["groups"]["test_group"]["execution_count"] == 5

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.listdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_load_ignores_non_runtime_files(self, mock_file, mock_listdir, mock_exists, mock_resolve):
        """Test that only runtime_*.yaml files are loaded."""
        mock_resolve.side_effect = lambda path: f"/config/{path}"

        def exists_side_effect(path):
            return path == "/config/runtime/scripts"

        mock_exists.side_effect = exists_side_effect
        mock_listdir.return_value = ["runtime_test.yaml", "other_file.yaml", "readme.txt", ".hidden.yaml"]

        runtime_data = {"scripts": {"test_script": {"last_run": "20240101_120000", "last_status": "success"}}}

        with patch("yaml.safe_load", return_value=runtime_data):
            result = load_runtime_state()

        # Should only load the runtime_test.yaml file
        assert len(result["scripts"]) == 1

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.listdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_load_handles_invalid_yaml(self, mock_file, mock_listdir, mock_exists, mock_resolve):
        """Test loading runtime state with invalid YAML file."""
        mock_resolve.side_effect = lambda path: f"/config/{path}"

        def exists_side_effect(path):
            return path == "/config/runtime/scripts"

        mock_exists.side_effect = exists_side_effect
        mock_listdir.return_value = ["runtime_bad.yaml"]

        # Simulate YAML error
        with patch("yaml.safe_load", side_effect=yaml.YAMLError("Invalid YAML")):
            result = load_runtime_state()

        # Should return empty state without crashing
        assert result == {"scripts": {}, "groups": {}}

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.listdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_load_handles_missing_scripts_key(self, mock_file, mock_listdir, mock_exists, mock_resolve):
        """Test loading runtime state when 'scripts' key is missing."""
        mock_resolve.side_effect = lambda path: f"/config/{path}"

        def exists_side_effect(path):
            return path == "/config/runtime/scripts"

        mock_exists.side_effect = exists_side_effect
        mock_listdir.return_value = ["runtime_test.yaml"]

        # Data without 'scripts' key
        runtime_data = {"other_key": "value"}

        with patch("yaml.safe_load", return_value=runtime_data):
            result = load_runtime_state()

        # Should still return empty scripts
        assert result["scripts"] == {}

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.listdir")
    @patch("builtins.open", new_callable=mock_open)
    def test_load_multiple_runtime_files(self, mock_file, mock_listdir, mock_exists, mock_resolve):
        """Test loading multiple runtime files and merging."""
        mock_resolve.side_effect = lambda path: f"/config/{path}"

        def exists_side_effect(path):
            return path == "/config/runtime/scripts"

        mock_exists.side_effect = exists_side_effect
        mock_listdir.return_value = ["runtime_file1.yaml", "runtime_file2.yaml"]

        # Simulate two files with different scripts
        call_count = [0]

        def safe_load_side_effect(f):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"scripts": {"script1": {"last_run": "time1", "last_status": "success"}}}
            else:
                return {"scripts": {"script2": {"last_run": "time2", "last_status": "failed"}}}

        with patch("yaml.safe_load", side_effect=safe_load_side_effect):
            result = load_runtime_state()

        # Should have both scripts
        assert "script1" in result["scripts"]
        assert "script2" in result["scripts"]


class TestSaveScriptRuntimeState:
    """Tests for save_script_runtime_state function."""

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_new_script_state(self, mock_file, mock_makedirs, mock_exists, mock_resolve):
        """Test saving runtime state for a new script."""
        mock_resolve.return_value = "/config/runtime/scripts/runtime_test.yaml"
        mock_exists.return_value = False

        with patch("yaml.dump") as mock_dump:
            save_script_runtime_state("test_script", "scripts/test.yaml", "20240101_120000", "success")

        # Verify directory creation
        mock_makedirs.assert_called_once()

        # Verify file write
        mock_file.assert_called()

        # Verify yaml dump was called with correct data
        mock_dump.assert_called_once()
        dumped_data = mock_dump.call_args[0][0]
        assert "scripts" in dumped_data
        assert "test_script" in dumped_data["scripts"]
        assert dumped_data["scripts"]["test_script"]["last_run"] == "20240101_120000"
        assert dumped_data["scripts"]["test_script"]["last_status"] == "success"

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_update_existing_script_state(self, mock_file, mock_makedirs, mock_exists, mock_resolve):
        """Test updating runtime state for an existing script."""
        mock_resolve.return_value = "/config/runtime/scripts/runtime_test.yaml"
        mock_exists.return_value = True

        # Existing data
        existing_data = {
            "scripts": {
                "test_script": {"last_run": "old_time", "last_status": "failed"},
                "other_script": {"last_run": "other_time", "last_status": "success"},
            }
        }

        with patch("yaml.safe_load", return_value=existing_data), patch("yaml.dump") as mock_dump:
            save_script_runtime_state("test_script", "scripts/test.yaml", "20240101_120000", "success")

        # Verify yaml dump was called
        dumped_data = mock_dump.call_args[0][0]

        # Should update test_script but keep other_script
        assert dumped_data["scripts"]["test_script"]["last_run"] == "20240101_120000"
        assert dumped_data["scripts"]["test_script"]["last_status"] == "success"
        assert "other_script" in dumped_data["scripts"]

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_handles_corrupted_existing_file(self, mock_file, mock_makedirs, mock_exists, mock_resolve):
        """Test saving when existing file is corrupted."""
        mock_resolve.return_value = "/config/runtime/scripts/runtime_test.yaml"
        mock_exists.return_value = True

        # Simulate corrupted file
        with patch("yaml.safe_load", side_effect=yaml.YAMLError("Corrupted")), patch("yaml.dump") as mock_dump:
            save_script_runtime_state("test_script", "scripts/test.yaml", "20240101_120000", "success")

        # Should create new data structure
        dumped_data = mock_dump.call_args[0][0]
        assert "scripts" in dumped_data
        assert "test_script" in dumped_data["scripts"]

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_runtime_filename_from_source(self, mock_file, mock_makedirs, mock_exists, mock_resolve):
        """Test that runtime filename is correctly derived from source file."""
        mock_resolve.return_value = "/config/runtime/scripts/runtime_custom.yaml"
        mock_exists.return_value = False

        with patch("yaml.dump"):
            save_script_runtime_state("test_script", "scripts/custom.yaml", "20240101_120000", "success")

        # Verify resolve_path was called with correct runtime filename
        expected_call = "runtime/scripts/runtime_custom.yaml"
        mock_resolve.assert_called_with(expected_call)


class TestSaveGroupRuntimeState:
    """Tests for save_group_runtime_state function."""

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_new_group_state(self, mock_file, mock_makedirs, mock_exists, mock_resolve):
        """Test saving runtime state for a new group."""
        mock_resolve.return_value = "/config/runtime/groups/runtime_test.yaml"
        mock_exists.return_value = False

        with patch("yaml.dump") as mock_dump:
            save_group_runtime_state(
                "test_group",
                "groups/test.yaml",
                "20240101_120000",
                "success",
                45.5,  # execution_time
                10,  # scripts_total
                8,  # scripts_successful
            )

        dumped_data = mock_dump.call_args[0][0]
        group_data = dumped_data["groups"]["test_group"]

        assert group_data["last_run"] == "20240101_120000"
        assert group_data["last_status"] == "success"
        assert group_data["execution_time_seconds"] == 45.5
        assert group_data["execution_count"] == 1
        assert group_data["scripts_total"] == 10
        assert group_data["scripts_successful"] == 8
        assert group_data["success_rate"] == 80.0

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_increments_execution_count(self, mock_file, mock_makedirs, mock_exists, mock_resolve):
        """Test that execution_count is incremented on each save."""
        mock_resolve.return_value = "/config/runtime/groups/runtime_test.yaml"
        mock_exists.return_value = True

        # Existing data with execution_count = 3
        existing_data = {
            "groups": {
                "test_group": {
                    "last_run": "old_time",
                    "last_status": "success",
                    "execution_count": 3,
                    "scripts_total": 5,
                    "scripts_successful": 5,
                }
            }
        }

        with patch("yaml.safe_load", return_value=existing_data), patch("yaml.dump") as mock_dump:
            save_group_runtime_state("test_group", "groups/test.yaml", "20240101_120000", "success", 30.0, 5, 4)

        dumped_data = mock_dump.call_args[0][0]
        assert dumped_data["groups"]["test_group"]["execution_count"] == 4

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_calculates_success_rate(self, mock_file, mock_makedirs, mock_exists, mock_resolve):
        """Test that success_rate is correctly calculated."""
        mock_resolve.return_value = "/config/runtime/groups/runtime_test.yaml"
        mock_exists.return_value = False

        test_cases = [
            (10, 8, 80.0),  # 8/10 = 80%
            (3, 3, 100.0),  # 3/3 = 100%
            (5, 0, 0.0),  # 0/5 = 0%
            (7, 5, 71.4),  # 5/7 = 71.4%
        ]

        for total, successful, expected_rate in test_cases:
            with patch("yaml.dump") as mock_dump:
                save_group_runtime_state(
                    "test_group", "groups/test.yaml", "20240101_120000", "partial", 30.0, total, successful
                )

            dumped_data = mock_dump.call_args[0][0]
            assert dumped_data["groups"]["test_group"]["success_rate"] == expected_rate

    @patch("core.runtime.resolve_path")
    @patch("core.runtime.os.path.exists")
    @patch("core.runtime.os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    def test_save_handles_zero_scripts(self, mock_file, mock_makedirs, mock_exists, mock_resolve):
        """Test handling when scripts_total is 0 (avoid division by zero)."""
        mock_resolve.return_value = "/config/runtime/groups/runtime_test.yaml"
        mock_exists.return_value = False

        with patch("yaml.dump") as mock_dump:
            save_group_runtime_state(
                "empty_group", "groups/test.yaml", "20240101_120000", "success", 0.0, 0, 0  # scripts_total = 0
            )

        dumped_data = mock_dump.call_args[0][0]
        # Should be 0.0, not raise ZeroDivisionError
        assert dumped_data["groups"]["empty_group"]["success_rate"] == 0.0


class TestMergeConfigWithRuntimeState:
    """Tests for merge_config_with_runtime_state function."""

    def test_merge_scripts_with_runtime_state(self):
        """Test merging script config with runtime state."""
        config = {
            "scripts": [
                {"name": "script1", "command": "echo 1", "description": "Test 1"},
                {"name": "script2", "command": "echo 2", "description": "Test 2"},
            ],
            "groups": [],
        }

        runtime_state = {
            "scripts": {"script1": {"last_run": "20240101_120000", "last_status": "success"}},
            "groups": {},
        }

        result = merge_config_with_runtime_state(config, runtime_state)

        # script1 should have runtime state
        assert result["scripts"][0]["last_run"] == "20240101_120000"
        assert result["scripts"][0]["last_status"] == "success"

        # script2 should have defaults
        assert result["scripts"][1]["last_run"] == ""
        assert result["scripts"][1]["last_status"] == "no logs"

    def test_merge_all_scripts_without_runtime_state(self):
        """Test merging when no runtime state exists."""
        config = {
            "scripts": [
                {"name": "script1", "command": "echo 1", "description": "Test 1"},
                {"name": "script2", "command": "echo 2", "description": "Test 2"},
            ],
            "groups": [],
        }

        runtime_state = {"scripts": {}, "groups": {}}

        result = merge_config_with_runtime_state(config, runtime_state)

        # All scripts should have defaults
        for script in result["scripts"]:
            assert script["last_run"] == ""
            assert script["last_status"] == "no logs"

    def test_merge_preserves_other_script_fields(self):
        """Test that merging preserves other fields in script config."""
        config = {
            "scripts": [
                {
                    "name": "script1",
                    "command": "echo test",
                    "description": "Test script",
                    "timeout": 300,
                    "custom_field": "value",
                }
            ],
            "groups": [],
        }

        runtime_state = {
            "scripts": {"script1": {"last_run": "20240101_120000", "last_status": "success"}},
            "groups": {},
        }

        result = merge_config_with_runtime_state(config, runtime_state)

        # Original fields should be preserved
        assert result["scripts"][0]["command"] == "echo test"
        assert result["scripts"][0]["description"] == "Test script"
        assert result["scripts"][0]["timeout"] == 300
        assert result["scripts"][0]["custom_field"] == "value"

        # Runtime state should be added
        assert result["scripts"][0]["last_run"] == "20240101_120000"
        assert result["scripts"][0]["last_status"] == "success"

    def test_merge_groups_with_runtime_state(self):
        """Test merging group config with runtime state."""
        config = {
            "scripts": [],
            "groups": [
                {"name": "group1", "scripts": ["script1", "script2"]},
                {"name": "group2", "scripts": ["script3"]},
            ],
        }

        runtime_state = {
            "scripts": {},
            "groups": {"group1": {"last_run": "20240101_120000", "last_status": "success", "execution_count": 5}},
        }

        result = merge_config_with_runtime_state(config, runtime_state)

        # Groups should be processed (currently no fields added)
        assert len(result["groups"]) == 2
        assert result["groups"][0]["name"] == "group1"

    def test_merge_empty_config(self):
        """Test merging empty config."""
        config = {"scripts": [], "groups": []}
        runtime_state = {"scripts": {}, "groups": {}}

        result = merge_config_with_runtime_state(config, runtime_state)

        assert result == {"scripts": [], "groups": []}

    def test_merge_returns_modified_config(self):
        """Test that merge returns the same config object (modified in place)."""
        config = {"scripts": [{"name": "script1", "command": "echo 1", "description": "Test"}], "groups": []}

        runtime_state = {
            "scripts": {"script1": {"last_run": "20240101_120000", "last_status": "success"}},
            "groups": {},
        }

        result = merge_config_with_runtime_state(config, runtime_state)

        # Should return the same object
        assert result is config


class TestRuntimeIntegration:
    """Integration tests for runtime module."""

    def test_full_save_load_cycle_scripts(self, temp_dir):
        """Test complete save and load cycle for script runtime state."""
        runtime_dir = Path(temp_dir) / "runtime" / "scripts"
        runtime_dir.mkdir(parents=True)

        runtime_file = runtime_dir / "runtime_test.yaml"

        with patch("core.runtime.resolve_path", return_value=str(runtime_file)):
            # Save state
            save_script_runtime_state("test_script", "scripts/test.yaml", "20240101_120000", "success")

            # Verify file exists
            assert runtime_file.exists()

            # Load and verify
            with open(runtime_file, "r") as f:
                content = f.read()
                assert "test_script" in content
                assert "20240101_120000" in content

    def test_full_save_load_cycle_groups(self, temp_dir):
        """Test complete save and load cycle for group runtime state."""
        runtime_dir = Path(temp_dir) / "runtime" / "groups"
        runtime_dir.mkdir(parents=True)

        runtime_file = runtime_dir / "runtime_test_group.yaml"

        with patch("core.runtime.resolve_path", return_value=str(runtime_file)):
            # Save state
            save_group_runtime_state("test_group", "groups/test_group.yaml", "20240101_120000", "success", 45.5, 10, 8)

            # Verify file exists
            assert runtime_file.exists()

            # Load and verify
            with open(runtime_file, "r") as f:
                data = yaml.safe_load(f)
                assert "test_group" in data["groups"]
                assert data["groups"]["test_group"]["success_rate"] == 80.0
