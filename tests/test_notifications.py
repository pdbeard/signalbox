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
