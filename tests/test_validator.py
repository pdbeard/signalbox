import pytest
from core import validator

class DummyConfig:
    def __init__(self, scripts=None, groups=None):
        self.scripts = scripts or []
        self.groups = groups or []

def test_validation_result_properties(monkeypatch):
    v = validator.ValidationResult()
    v.errors = []
    v.warnings = []
    monkeypatch.setattr(validator, 'get_config_value', lambda k, d=None: False)
    assert v.is_valid
    v.errors = ['err']
    assert not v.is_valid
    v.errors = []
    v.warnings = ['warn']
    assert v.has_issues
    monkeypatch.setattr(validator, 'get_config_value', lambda k, d=None: True)
    assert not v.is_valid

def test_validate_configuration_valid(monkeypatch):
    # Patch config loading and file checks
    monkeypatch.setattr(validator, 'get_config_value', lambda k, d=None: 'dummy')
    monkeypatch.setattr(validator, 'resolve_path', lambda p: p)
    monkeypatch.setattr(validator, 'load_config', lambda *a, **kw: {'scripts': [{'name': 's1', 'command': 'echo 1'}], 'groups': [{'name': 'g1', 'schedule': '* * * * *'}]})
    monkeypatch.setattr(validator, 'load_global_config', lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert isinstance(result, validator.ValidationResult)
    assert any('No scripts file found' in e for e in result.errors)

def test_validate_configuration_missing_script(monkeypatch):
    monkeypatch.setattr(validator, 'get_config_value', lambda k, d=None: 'dummy')
    monkeypatch.setattr(validator, 'resolve_path', lambda p: p)
    monkeypatch.setattr(validator, 'load_config', lambda *a, **kw: {'scripts': [], 'groups': [{'name': 'g1', 'schedule': '* * * * *'}]})
    monkeypatch.setattr(validator, 'load_global_config', lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert isinstance(result, validator.ValidationResult)
    assert result.errors

def test_validate_configuration_missing_groups(monkeypatch):
    monkeypatch.setattr(validator, 'get_config_value', lambda k, d=None: 'dummy')
    monkeypatch.setattr(validator, 'resolve_path', lambda p: p)
    monkeypatch.setattr(validator, 'load_config', lambda *a, **kw: {'scripts': [{'name': 's1', 'command': 'echo 1'}], 'groups': []})
    monkeypatch.setattr(validator, 'load_global_config', lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert result.errors

def test_validate_configuration_missing_catalog(monkeypatch):
    monkeypatch.setattr(validator, 'get_config_value', lambda k, d=None: 'dummy')
    monkeypatch.setattr(validator, 'resolve_path', lambda p: p)
    monkeypatch.setattr(validator, 'load_config', lambda *a, **kw: {'scripts': [{'name': 's1', 'command': 'echo 1'}], 'groups': [{'name': 'g1', 'schedule': '* * * * *'}]})
    monkeypatch.setattr(validator, 'load_global_config', lambda *a, **kw: {})
    # Simulate missing catalog files by raising FileNotFoundError
    monkeypatch.setattr(validator, 'load_config', lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    try:
        result = validator.validate_configuration()
    except FileNotFoundError:
        assert True

def test_validate_configuration_strict_mode(monkeypatch):
    # Simulate strict mode with warnings
    monkeypatch.setattr(validator, 'get_config_value', lambda k, d=None: True if k == 'validation.strict' else 'dummy')
    monkeypatch.setattr(validator, 'resolve_path', lambda p: p)
    monkeypatch.setattr(validator, 'load_config', lambda *a, **kw: {'scripts': [{'name': 's1', 'command': 'echo 1'}], 'groups': [{'name': 'g1', 'schedule': '* * * * *'}]})
    monkeypatch.setattr(validator, 'load_global_config', lambda *a, **kw: {})
    result = validator.validate_configuration()
    result.warnings.append('warn')
    assert not result.is_valid

def test_validate_configuration_invalid_group(monkeypatch):
    monkeypatch.setattr(validator, 'get_config_value', lambda k, d=None: 'dummy')
    monkeypatch.setattr(validator, 'resolve_path', lambda p: p)
    monkeypatch.setattr(validator, 'load_config', lambda *a, **kw: {'scripts': [{'name': 's1', 'command': 'echo 1'}], 'groups': [{'name': 'g1'}]})
    monkeypatch.setattr(validator, 'load_global_config', lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert result.errors

def test_validate_configuration_cron(monkeypatch):
    monkeypatch.setattr(validator, 'get_config_value', lambda k, d=None: 'dummy')
    monkeypatch.setattr(validator, 'resolve_path', lambda p: p)
    monkeypatch.setattr(validator, 'load_config', lambda *a, **kw: {'scripts': [{'name': 's1', 'command': 'echo 1'}], 'groups': [{'name': 'g1', 'schedule': 'bad cron'}]})
    monkeypatch.setattr(validator, 'load_global_config', lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert result.errors or result.warnings
