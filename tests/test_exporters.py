import os
import tempfile
import shutil
import pytest
from core import exporters

class DummyGroup(dict):
    pass

def test_validate_group_for_export_valid():
    group = {'schedule': '* * * * *'}
    valid, error = exporters.validate_group_for_export(group, 'test')
    assert valid
    assert error is None

def test_validate_group_for_export_missing_group():
    valid, error = exporters.validate_group_for_export(None, 'missing')
    assert not valid
    assert "not found" in error

def test_validate_group_for_export_no_schedule():
    group = {'foo': 1}
    valid, error = exporters.validate_group_for_export(group, 'nosched')
    assert not valid
    assert "no schedule" in error

def test_get_python_executable():
    exe = exporters.get_python_executable()
    assert exe.endswith('python') or 'python' in exe

def test_get_signalbox_command_dev(monkeypatch):
    monkeypatch.setattr('shutil.which', lambda name: None)
    # Simulate signalbox.py exists
    core_dir = os.path.dirname(os.path.abspath(exporters.__file__))
    project_root = os.path.dirname(core_dir)
    signalbox_py = os.path.join(project_root, "signalbox.py")
    monkeypatch.setattr(os.path, "exists", lambda path: path == signalbox_py)
    cmd = exporters.get_signalbox_command()
    assert "python" in cmd and "signalbox.py" in cmd

def test_get_signalbox_command_cli(monkeypatch):
    monkeypatch.setattr('shutil.which', lambda name: '/usr/local/bin/signalbox')
    cmd = exporters.get_signalbox_command()
    assert cmd == "signalbox"

def test_get_script_dir_cli(monkeypatch):
    monkeypatch.setattr('shutil.which', lambda name: '/usr/local/bin/signalbox')
    path = exporters.get_script_dir()
    assert path.endswith('signalbox')

def test_get_script_dir_dev(monkeypatch):
    monkeypatch.setattr('shutil.which', lambda name: None)
    path = exporters.get_script_dir()
    assert os.path.isdir(path)

def test_generate_systemd_service():
    group = {'description': 'desc', 'schedule': '* * * * *'}
    content = exporters.generate_systemd_service(group, 'g1')
    assert '[Unit]' in content and 'ExecStart=' in content

def test_generate_systemd_timer():
    group = {'description': 'desc', 'schedule': '* * * * *'}
    content = exporters.generate_systemd_timer(group, 'g1')
    assert '[Timer]' in content and 'OnCalendar=' in content

def test_generate_cron_entry():
    group = {'description': 'desc', 'schedule': '* * * * *'}
    entry = exporters.generate_cron_entry(group, 'g1')
    assert 'run-group g1' in entry

def test_export_systemd(monkeypatch, tmp_path):
    group = {'description': 'desc', 'schedule': '* * * * *'}
    monkeypatch.setattr(exporters, 'get_config_value', lambda k, d=None: str(tmp_path))
    result = exporters.export_systemd(group, 'g1')
    assert result.success
    for f in result.files:
        assert os.path.exists(f)
    shutil.rmtree(os.path.join(tmp_path, 'g1'))

def test_export_systemd_invalid():
    group = {}
    result = exporters.export_systemd(group, 'g1')
    assert not result.success
    assert result.error

def test_export_cron(monkeypatch, tmp_path):
    group = {'description': 'desc', 'schedule': '* * * * *'}
    monkeypatch.setattr(exporters, 'get_config_value', lambda k, d=None: str(tmp_path))
    result = exporters.export_cron(group, 'g1')
    assert result.success
    for f in result.files:
        assert os.path.exists(f)
    shutil.rmtree(os.path.join(tmp_path, 'g1'))

def test_export_cron_invalid():
    group = {}
    result = exporters.export_cron(group, 'g1')
    assert not result.success
    assert result.error

def test_get_systemd_install_instructions():
    instr = exporters.get_systemd_install_instructions('f1', 'f2', 'g1', user=True)
    assert any('systemctl' in line for line in instr)
    instr2 = exporters.get_systemd_install_instructions('f1', 'f2', 'g1', user=False)
    assert any('sudo' in line for line in instr2)

def test_get_cron_install_instructions():
    group = {'description': 'desc'}
    instr = exporters.get_cron_install_instructions('f1', 'entry', group)
    assert any('crontab' in line for line in instr)
