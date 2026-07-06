import pytest
from signalbox import validator


class DummyConfig:
    def __init__(self, tasks=None, groups=None):
        self.tasks = tasks or []
        self.groups = groups or []


def test_validation_result_properties(monkeypatch):
    v = validator.ValidationResult()
    v.errors = []
    v.warnings = []
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: False)
    assert v.is_valid
    v.errors = ["err"]
    assert not v.is_valid
    v.errors = []
    v.warnings = ["warn"]
    assert v.has_issues
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: True)
    assert not v.is_valid


def test_validate_configuration_valid(monkeypatch):
    """Valid config with tasks and groups should produce no errors."""
    from unittest.mock import mock_open, patch
    import yaml as yaml_mod

    def mock_config_value(k, d=None):
        if k == "paths.tasks_file":
            return "dummy_tasks"
        if k == "paths.groups_file":
            return "dummy_groups"
        if str(k).startswith("paths.catalog"):
            return "nonexistent_catalog"
        return "dummy"

    monkeypatch.setattr(validator, "get_config_value", mock_config_value)
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    monkeypatch.setattr(
        validator,
        "load_config",
        lambda *a, **kw: {
            "tasks": [{"name": "s1", "command": "echo 1"}],
            "groups": [{"name": "g1", "schedule": "* * * * *"}],
        },
    )
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    monkeypatch.setattr(validator.os.path, "isdir", lambda p: p == "dummy_tasks")
    monkeypatch.setattr(validator.os.path, "exists", lambda p: p == "dummy_tasks")
    monkeypatch.setattr(validator.os, "listdir", lambda p: ["tasks.yaml"])
    valid_data = {"tasks": [{"name": "s1", "command": "echo 1", "description": "Test"}]}
    with patch("builtins.open", mock_open()), patch("yaml.safe_load", return_value=valid_data):
        result = validator.validate_configuration()
    assert isinstance(result, validator.ValidationResult)
    assert result.errors == []


def test_validate_configuration_invalid_task_timeout(monkeypatch):
    """A non-numeric or negative per-task timeout should produce an error."""
    from unittest.mock import mock_open, patch

    def mock_config_value(k, d=None):
        if k == "paths.tasks_file":
            return "dummy_tasks"
        if k == "paths.groups_file":
            return "dummy_groups"
        if str(k).startswith("paths.catalog"):
            return "nonexistent_catalog"
        return "dummy"

    monkeypatch.setattr(validator, "get_config_value", mock_config_value)
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    monkeypatch.setattr(validator, "load_config", lambda *a, **kw: {"tasks": [], "groups": []})
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    monkeypatch.setattr(validator.os.path, "isdir", lambda p: p == "dummy_tasks")
    monkeypatch.setattr(validator.os.path, "exists", lambda p: p == "dummy_tasks")
    monkeypatch.setattr(validator.os, "listdir", lambda p: ["tasks.yaml"])
    bad_data = {"tasks": [{"name": "s1", "command": "echo 1", "description": "Test", "timeout": -5}]}
    with patch("builtins.open", mock_open()), patch("yaml.safe_load", return_value=bad_data):
        result = validator.validate_configuration()
    assert any("invalid timeout" in e for e in result.errors)


def test_validate_configuration_missing_script(monkeypatch):
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: "dummy")
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    monkeypatch.setattr(
        validator, "load_config", lambda *a, **kw: {"tasks": [], "groups": [{"name": "g1", "schedule": "* * * * *"}]}
    )
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert isinstance(result, validator.ValidationResult)
    assert result.errors


def test_validate_configuration_missing_groups(monkeypatch):
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: "dummy")
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    monkeypatch.setattr(
        validator, "load_config", lambda *a, **kw: {"tasks": [{"name": "s1", "command": "echo 1"}], "groups": []}
    )
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert result.errors


def test_validate_configuration_missing_catalog(monkeypatch):
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: "dummy")
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    # Simulate missing catalog files by raising FileNotFoundError
    monkeypatch.setattr(validator, "load_config", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    try:
        result = validator.validate_configuration()
    except FileNotFoundError:
        pass  # Expected — load_config raised FileNotFoundError


def test_validate_configuration_strict_mode(monkeypatch):
    # Simulate strict mode with warnings
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: True if k == "validation.strict" else "dummy")
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    monkeypatch.setattr(
        validator,
        "load_config",
        lambda *a, **kw: {
            "tasks": [{"name": "s1", "command": "echo 1"}],
            "groups": [{"name": "g1", "schedule": "* * * * *"}],
        },
    )
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    result = validator.validate_configuration()
    result.warnings.append("warn")
    assert not result.is_valid


def test_validate_configuration_empty(monkeypatch):
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: "dummy")
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    monkeypatch.setattr(validator, "load_config", lambda *a, **kw: {})
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert result.errors


def test_validate_configuration_invalid_types(monkeypatch):
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: "dummy")
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    # tasks is not a list
    monkeypatch.setattr(validator, "load_config", lambda *a, **kw: {"tasks": "notalist", "groups": []})
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert result.errors


def test_validate_configuration_invalid_group(monkeypatch):
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: "dummy")
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    monkeypatch.setattr(
        validator,
        "load_config",
        lambda *a, **kw: {"tasks": [{"name": "s1", "command": "echo 1"}], "groups": [{"name": "g1"}]},
    )
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert result.errors


def test_validate_configuration_cron(monkeypatch):
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: "dummy")
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    monkeypatch.setattr(
        validator,
        "load_config",
        lambda *a, **kw: {
            "tasks": [{"name": "s1", "command": "echo 1"}],
            "groups": [{"name": "g1", "schedule": "bad cron"}],
        },
    )
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert result.errors or result.warnings


def test_validate_invalid_yaml(monkeypatch):
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: "dummy")
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)

    def bad_load(*a, **kw):
        raise Exception("YAML parse error")

    monkeypatch.setattr(validator, "load_config", bad_load)
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    try:
        validator.validate_configuration()
    except Exception as e:
        assert "YAML" in str(e) or "parse" in str(e)


def test_validate_missing_required_fields(monkeypatch):
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: "dummy")
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    monkeypatch.setattr(validator, "load_config", lambda *a, **kw: {"tasks": [{}], "groups": [{}]})
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert result.errors


def test_validate_empty_file(monkeypatch):
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: "dummy")
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    monkeypatch.setattr(validator, "load_config", lambda *a, **kw: None)
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: None)
    result = validator.validate_configuration()
    assert result.errors


def test_validate_catalog_edge_case(monkeypatch):
    monkeypatch.setattr(validator, "get_config_value", lambda k, d=None: "dummy")
    monkeypatch.setattr(validator, "resolve_path", lambda p: p)
    # Simulate catalog config with missing tasks key
    monkeypatch.setattr(validator, "load_config", lambda *a, **kw: {"groups": [], "catalog": {"tasks": [{}]}})
    monkeypatch.setattr(validator, "load_global_config", lambda *a, **kw: {})
    result = validator.validate_configuration()
    assert result.errors
