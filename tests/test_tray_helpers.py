"""Tests for the tray app's non-GUI helpers (skipped when PyQt6 is not installed)."""

import json
import os
import sys
from datetime import datetime

import pytest

pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError)

from signalbox import tray_app  # noqa: E402
from signalbox.config import reset_config  # noqa: E402


def test_parse_last_run_uses_configured_timestamp_format(sb_home):
    sb_home.write_settings({"logging": {"timestamp_format": "%Y-%m-%dT%H.%M.%S"}})
    expected = int(datetime(2026, 1, 2, 3, 4, 5).timestamp())
    assert tray_app._parse_last_run_to_ts("2026-01-02T03.04.05") == expected


def test_parse_last_run_handles_default_and_missing():
    expected = int(datetime(2026, 1, 2, 3, 4, 5).timestamp())
    assert tray_app._parse_last_run_to_ts("20260102_030405_123456") == expected
    assert tray_app._parse_last_run_to_ts("") == 0
    assert tray_app._parse_last_run_to_ts("Never") == 0


def test_signalbox_command_uses_same_python_and_config_home(sb_home):
    command, env = tray_app._signalbox_command("task", "run", "a")
    assert command == [sys.executable, "-m", "signalbox", "task", "run", "a"]
    assert env["SIGNALBOX_HOME"] == str(sb_home.path)


def test_tray_state_lives_in_config_home(sb_home, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    tray_app._save_tray_state({"ignore_failures_before": 42})
    assert json.loads((sb_home.path / "runtime" / "tray_state.json").read_text()) == {"ignore_failures_before": 42}
    assert tray_app._load_tray_state() == {"ignore_failures_before": 42}


def test_tray_state_falls_back_to_legacy_file(sb_home, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".signalbox_tray_state.json").write_text('{"ignore_failures_before": 7}')
    reset_config()
    assert tray_app._load_tray_state() == {"ignore_failures_before": 7}


def test_current_state_ignores_deleted_tasks(sb_home):
    from signalbox.runtime import save_task_runtime_state

    sb_home.write_tasks([{"name": "kept", "command": "true", "description": "d"}])
    source = str(sb_home.config_dir / "tasks" / "tasks.yaml")
    save_task_runtime_state("kept", source, "20260102_030405_000000", "success")
    save_task_runtime_state("deleted", source, "20260102_030405_000000", "failed")

    _, runtime_state = tray_app._current_state()

    assert list(runtime_state["tasks"]) == ["kept"]
    assert os.path.exists(source)
