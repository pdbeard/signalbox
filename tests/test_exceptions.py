import pytest
from core import exceptions

def test_signalbox_error():
    e = exceptions.SignalboxError('msg', exit_code=42)
    assert str(e) == 'msg'
    assert e.exit_code == 42

def test_configuration_error():
    e = exceptions.ConfigurationError('bad config')
    assert isinstance(e, exceptions.SignalboxError)
    assert e.exit_code == 2

def test_script_not_found_error():
    e = exceptions.ScriptNotFoundError('myscript')
    assert 'myscript' in str(e)
    assert e.exit_code == 3

def test_group_not_found_error():
    e = exceptions.GroupNotFoundError('mygroup')
    assert 'mygroup' in str(e)
    assert e.exit_code == 3

def test_execution_error():
    e = exceptions.ExecutionError('myscript', 'fail')
    assert 'myscript' in str(e)
    assert 'fail' in str(e)
    assert e.exit_code == 4

def test_execution_timeout_error():
    e = exceptions.ExecutionTimeoutError('myscript', 10)
    assert 'myscript' in str(e)
    assert 'timed out' in str(e)
    assert e.exit_code == 4

def test_validation_error():
    e = exceptions.ValidationError('bad')
    assert isinstance(e, exceptions.SignalboxError)
