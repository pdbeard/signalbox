import os
import tempfile
import shutil
import pytest
from signalbox import exporters


class DummyGroup(dict):
    pass


def test_validate_group_for_export_valid():
    group = {"schedule": "* * * * *"}
    valid, error = exporters.validate_group_for_export(group, "test")
    assert valid
    assert error is None


def test_validate_group_for_export_missing_group():
    valid, error = exporters.validate_group_for_export(None, "missing")
    assert not valid
    assert "not found" in error


def test_validate_group_for_export_no_schedule():
    group = {"foo": 1}
    valid, error = exporters.validate_group_for_export(group, "nosched")
    assert not valid
    assert "no schedule" in error


def test_get_python_executable():
    exe = exporters.get_python_executable()
    assert exe.endswith("python") or "python" in exe


def test_get_signalbox_command_dev(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    cmd = exporters.get_signalbox_command()
    assert cmd.endswith(" -m signalbox")
    assert "python" in cmd


def test_get_signalbox_command_cli(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/signalbox")
    cmd = exporters.get_signalbox_command()
    # Absolute path: cron and systemd don't search the user's PATH
    assert cmd == "/usr/local/bin/signalbox"


def test_get_task_dir_uses_config_home(monkeypatch, tmp_path):
    monkeypatch.setattr(exporters, "find_config_home", lambda: str(tmp_path))
    assert exporters.get_task_dir() == str(tmp_path)


@pytest.mark.parametrize(
    "cron, expected",
    [
        ("* * * * *", "*-*-* *:*:00"),
        ("0 * * * *", "*-*-* *:0:00"),
        ("*/5 * * * *", "*-*-* *:0/5:00"),
        ("30 2 * * *", "*-*-* 2:30:00"),
        ("0 9-17 * * 1-5", "Mon..Fri *-*-* 9..17:0:00"),
        ("0 0 1 */3 *", "*-1/3-1 0:0:00"),
        ("15,45 * * * 0,6", "Sun,Sat *-*-* *:15,45:00"),
        ("0 8 * * mon", "Mon *-*-* 8:0:00"),
        ("@daily", "daily"),
        ("@hourly", "hourly"),
    ],
)
def test_cron_to_oncalendar(cron, expected):
    assert exporters.cron_to_oncalendar(cron) == expected


@pytest.mark.parametrize("cron", ["* * *", "0 0 1 * 1", "0 0 * jan *", "0 1-5/2 * * *", "0 0 * * */2"])
def test_cron_to_oncalendar_unsupported(cron):
    with pytest.raises(ValueError):
        exporters.cron_to_oncalendar(cron)


def test_generate_systemd_service(monkeypatch, tmp_path):
    monkeypatch.setattr(exporters, "find_config_home", lambda: str(tmp_path))
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/signalbox")
    group = {"description": "desc", "schedule": "* * * * *"}
    content = exporters.generate_systemd_service(group, "g1")
    assert "[Unit]" in content
    assert "ExecStart=/usr/local/bin/signalbox group run g1" in content
    assert f"SIGNALBOX_HOME={tmp_path}" in content


def test_generate_systemd_timer():
    group = {"description": "desc", "schedule": "*/15 * * * *"}
    content = exporters.generate_systemd_timer(group, "g1")
    assert "[Timer]" in content
    assert "OnCalendar=*-*-* *:0/15:00" in content


def test_generate_cron_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(exporters, "find_config_home", lambda: str(tmp_path))
    group = {"description": "desc", "schedule": "* * * * *"}
    entry = exporters.generate_cron_entry(group, "g1")
    assert entry.startswith("* * * * * ")
    assert "group run g1" in entry
    assert f"SIGNALBOX_HOME={tmp_path}" in entry


def test_export_systemd(monkeypatch, tmp_path):
    group = {"description": "desc", "schedule": "* * * * *"}
    monkeypatch.setattr(exporters, "get_config_value", lambda k, d=None: str(tmp_path))
    result = exporters.export_systemd(group, "g1")
    assert result.success
    for f in result.files:
        assert os.path.exists(f)
    shutil.rmtree(os.path.join(tmp_path, "g1"))


def test_export_systemd_unconvertible_schedule(monkeypatch, tmp_path):
    group = {"description": "desc", "schedule": "0 0 1 * 1"}
    monkeypatch.setattr(exporters, "get_config_value", lambda k, d=None: str(tmp_path))
    result = exporters.export_systemd(group, "g1")
    assert not result.success
    assert "day-of-week" in result.error
    assert not os.path.exists(os.path.join(tmp_path, "g1"))


def test_export_systemd_invalid():
    group = {}
    result = exporters.export_systemd(group, "g1")
    assert not result.success
    assert result.error


def test_export_cron(monkeypatch, tmp_path):
    group = {"description": "desc", "schedule": "* * * * *"}
    monkeypatch.setattr(exporters, "get_config_value", lambda k, d=None: str(tmp_path))
    result = exporters.export_cron(group, "g1")
    assert result.success
    for f in result.files:
        assert os.path.exists(f)
    shutil.rmtree(os.path.join(tmp_path, "g1"))


def test_export_cron_invalid():
    group = {}
    result = exporters.export_cron(group, "g1")
    assert not result.success
    assert result.error


def test_get_systemd_install_instructions():
    instr = exporters.get_systemd_install_instructions("f1", "f2", "g1", user=True)
    assert any("systemctl" in line for line in instr)
    instr2 = exporters.get_systemd_install_instructions("f1", "f2", "g1", user=False)
    assert any("sudo" in line for line in instr2)


def test_get_cron_install_instructions():
    group = {"description": "desc"}
    instr = exporters.get_cron_install_instructions("f1", "entry", group)
    assert any("crontab" in line for line in instr)
