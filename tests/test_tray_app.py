"""Smoke tests for the tray app with a real Qt event loop, headless (skipped without PyQt6)."""

import os
from datetime import datetime, timedelta

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError)

from signalbox import tray_app  # noqa: E402
from signalbox.helpers import format_timestamp  # noqa: E402
from signalbox.runtime import (  # noqa: E402
    load_tray_state,
    save_group_runtime_state,
    save_task_runtime_state,
    setting_with_tray_override,
)


def menu_texts(tray):
    return [action.text() for action in tray.menu.actions()]


@pytest.fixture
def home(sb_home, monkeypatch):
    opened = []
    monkeypatch.setattr(tray_app, "_open", opened.append)
    sb_home.opened = opened
    sb_home.write_tasks([{"name": "ok", "command": "true"}, {"name": "bad", "command": "false"}])
    sb_home.write_groups([{"name": "every15", "tasks": ["ok"], "schedule": "*/15 * * * *"}])
    return sb_home


def test_shows_failures_overdue_groups_and_opens_logs(home):
    source = str(home.config_dir / "tasks" / "tasks.yaml")
    recent = format_timestamp(datetime.now() - timedelta(minutes=1))
    save_task_runtime_state("ok", source, recent, "success")
    save_task_runtime_state("bad", source, recent, "failed")
    old = format_timestamp(datetime.now() - timedelta(hours=3))
    save_group_runtime_state("every15", str(home.config_dir / "groups" / "groups.yaml"), old, "success", 1, 1, 1)
    log_dir = home.path / "logs" / "bad"
    log_dir.mkdir(parents=True)
    (log_dir / f"{recent}.log").write_text("Return code: 1\n")

    tray = tray_app.SignalboxTray()

    assert tray.status["colour"] == "red"
    assert "1 failed: bad" in tray.tray.toolTip() and "1 overdue: every15" in tray.tray.toolTip()
    texts = menu_texts(tray)
    assert any(t.startswith("✗ bad") for t in texts)
    assert any(t.startswith("⚠ every15") and "overdue" in t for t in texts)
    bad = next(a for a in tray.menu.actions() if a.text().startswith("✗ bad"))
    bad.trigger()
    assert home.opened == [str(log_dir / f"{recent}.log")]


def test_clear_errors_turns_failures_green_and_switch_mutes_both_notification_kinds(home):
    source = str(home.config_dir / "tasks" / "tasks.yaml")
    save_task_runtime_state("bad", source, format_timestamp(datetime.now() - timedelta(minutes=1)), "failed")
    tray = tray_app.SignalboxTray()
    assert tray.status["colour"] == "red"

    tray._clear_errors()
    assert tray.status["colour"] == "green"
    assert load_tray_state()["ignore_failures_before"] > 0

    next(a for a in tray.menu.actions() if a.text() == "Notifications").setChecked(False)
    assert setting_with_tray_override("alerts.notifications.enabled", True) is False
    assert setting_with_tray_override("group_notifications.enabled", True) is False


def test_unreadable_state_keeps_last_view(home, monkeypatch):
    tray = tray_app.SignalboxTray()
    before = tray.status

    def broken(**_kwargs):
        raise ValueError("half-written file")

    icons = []
    real_icon = tray_app.QIcon
    monkeypatch.setattr(tray_app, "QIcon", lambda path: icons.append(os.path.basename(path)) or real_icon(path))
    monkeypatch.setattr(tray_app, "read_status", broken)
    tray.refresh()

    assert tray.status is before
    assert "half-written file" in tray.tray.toolTip()
    assert icons == ["yellow.png"]  # never green while it cannot see the state


def test_text_poll_interval_falls_back_instead_of_crashing(home):
    home.write_settings({"tray": {"poll_interval": "30"}})
    tray = tray_app.SignalboxTray()
    assert tray.timer.interval() == 30_000


def test_notifies_once_when_a_group_becomes_overdue(home, monkeypatch):
    home.write_settings({"group_notifications": {"enabled": True}})
    sent = []
    monkeypatch.setattr(tray_app, "send_notification", lambda title, message: sent.append(message))
    old = format_timestamp(datetime.now() - timedelta(hours=3))
    save_group_runtime_state("every15", str(home.config_dir / "groups" / "groups.yaml"), old, "success", 1, 1, 1)

    tray = tray_app.SignalboxTray()
    tray.refresh()  # still overdue: no second notification

    assert sent == ["Did not run when due: every15"]
