import sys
import types
import pytest
from core import notifications

def test_send_notification_macos(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    called = {}
    def fake_macos(title, message):
        called['ok'] = (title, message)
        return True
    monkeypatch.setattr(notifications, '_send_macos_notification', fake_macos)
    assert notifications.send_notification('t', 'm')
    assert called['ok'] == ('t', 'm')

def test_send_notification_linux(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Linux')
    called = {}
    def fake_linux(title, message, urgency='normal'):
        called['ok'] = (title, message, urgency)
        return True
    monkeypatch.setattr(notifications, '_send_linux_notification', fake_linux)
    assert notifications.send_notification('t', 'm', urgency='critical')
    assert called['ok'] == ('t', 'm', 'critical')

def test_send_notification_unsupported(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Windows')
    assert notifications.send_notification('t', 'm') is False

def test_send_notification_exception(monkeypatch):
    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    def raise_exc(*a, **k):
        raise RuntimeError('fail')
    monkeypatch.setattr(notifications, '_send_macos_notification', raise_exc)
    assert notifications.send_notification('t', 'm') is False


import subprocess

def test_send_macos_notification_success(monkeypatch):
    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stderr = ''
        return Result()
    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert notifications._send_macos_notification('t', 'm') is True

def test_send_macos_notification_failure(monkeypatch):
    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 1
            stderr = 'fail'
        return Result()
    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert notifications._send_macos_notification('t', 'm') is False

def test_send_linux_notification_success(monkeypatch):
    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0
            stderr = ''
        return Result()
    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert notifications._send_linux_notification('t', 'm') is True

def test_send_linux_notification_no_notify_send(monkeypatch):
    calls = []
    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 1 if 'which' in cmd else 0
            stderr = 'fail'
        calls.append(cmd)
        return Result()
    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert notifications._send_linux_notification('t', 'm') is False

def test_send_linux_notification_fail_notify_send(monkeypatch):
    def fake_run(cmd, **kwargs):
        class Result:
            returncode = 0 if 'which' in cmd else 1
            stderr = 'fail'
        return Result()
    monkeypatch.setattr(subprocess, 'run', fake_run)
    assert notifications._send_linux_notification('t', 'm') is False
