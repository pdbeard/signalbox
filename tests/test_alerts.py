import builtins
import json
import os
import pytest
from signalbox import alerts
from datetime import datetime, timedelta


def test_check_alert_patterns_and_save(tmp_path, monkeypatch):
    # Setup: create a fake script config with alerts
    script_name = "test_script"
    script_config = {
        "alerts": [
            {"pattern": "ALERT: Disk usage HIGH", "message": "Disk usage is above 80%!", "severity": "critical"},
            {"pattern": "Disk usage OK", "message": "Disk usage is normal.", "severity": "info"},
        ]
    }
    output = "Checking disk space...\nALERT: Disk usage HIGH: 85% (/ 10G free)\n"

    log_dir = tmp_path / "logs"
    monkeypatch.setattr(alerts, "get_resolved_log_dir", lambda: str(log_dir))

    # Check alert patterns
    triggered = alerts.check_alert_patterns(script_name, script_config, output)
    assert len(triggered) == 1
    assert triggered[0]["severity"] == "critical"
    assert "Disk usage is above 80%" in triggered[0]["message"]

    # Save alert
    alerts.save_alert(script_name, triggered[0])
    alert_log = log_dir / script_name / "alerts" / "alerts.jsonl"
    assert alert_log.exists()
    with open(alert_log) as f:
        lines = f.readlines()
    assert len(lines) == 1
    assert "Disk usage is above 80%" in lines[0]


def test_load_alerts_unreadable_file(tmp_path, monkeypatch):
    """Test loading alerts raises IOError when file is unreadable."""
    script_name = "unreadable"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(alerts, "get_resolved_log_dir", lambda: str(log_dir))
    alerts_dir = log_dir / script_name / "alerts"
    os.makedirs(alerts_dir)
    alert_log = alerts_dir / "alerts.jsonl"
    with open(alert_log, "w") as f:
        f.write("{}\n")
    # Patch open to raise IOError
    orig_open = builtins.open

    def bad_open(*a, **kw):
        if a[0] == str(alert_log):
            raise IOError("unreadable")
        return orig_open(*a, **kw)

    monkeypatch.setattr(builtins, "open", bad_open)
    with pytest.raises(OSError):
        alerts.load_alerts(task_name=script_name)


def test_save_alert_missing_dir(tmp_path, monkeypatch):
    """Test saving alert when directory does not exist."""
    script_name = "missingdir"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(alerts, "get_resolved_log_dir", lambda: str(log_dir))
    alert = {
        "pattern": "p",
        "message": "m",
        "severity": "info",
        "timestamp": alerts.format_timestamp(datetime.now()),
        "script_name": script_name,
    }
    # Directory does not exist, should be created
    alerts.save_alert(script_name, alert)
    alert_log = log_dir / script_name / "alerts" / "alerts.jsonl"
    assert alert_log.exists()


def test_check_alert_patterns_invalid_regex(capsys):
    """An invalid pattern is skipped with a warning; valid patterns still match."""
    script_name = "s"
    script_config = {
        "alerts": [
            {"pattern": "[unclosed", "message": "bad regex"},
            {"pattern": "any", "message": "good"},
        ]
    }
    triggered = alerts.check_alert_patterns(script_name, script_config, "anything")
    assert [a["message"] for a in triggered] == ["good"]
    assert "Invalid alert pattern" in capsys.readouterr().err


def test_load_alerts_with_corrupt_json(tmp_path, monkeypatch):
    """Test loading alerts with invalid/corrupt JSON lines."""
    script_name = "corrupt_script"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(alerts, "get_resolved_log_dir", lambda: str(log_dir))
    alerts_dir = log_dir / script_name / "alerts"
    os.makedirs(alerts_dir)
    alert_log = alerts_dir / "alerts.jsonl"
    with open(alert_log, "w") as f:
        f.write("{bad json}\n")
        f.write(
            json.dumps(
                {
                    "message": "ok",
                    "severity": "info",
                    "timestamp": alerts.format_timestamp(datetime.now()),
                    "task_name": script_name,
                }
            )
            + "\n"
        )
    loaded = alerts.load_alerts(task_name=script_name)
    assert any(a["message"] == "ok" for a in loaded)


def test_prune_alerts_by_severity_and_time(tmp_path, monkeypatch):
    """Test pruning alerts by time cutoff."""
    script_name = "prune_script"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(alerts, "get_resolved_log_dir", lambda: str(log_dir))
    alerts_dir = log_dir / script_name / "alerts"
    os.makedirs(alerts_dir)
    alert_log = alerts_dir / "alerts.jsonl"
    now = datetime.now()
    # Write alerts with different timestamps
    alert_data = [
        {
            "pattern": "A",
            "message": "Critical",
            "severity": "critical",
            "timestamp": alerts.format_timestamp(now - timedelta(days=10)),
            "task_name": script_name,
        },
        {
            "pattern": "B",
            "message": "Info",
            "severity": "info",
            "timestamp": alerts.format_timestamp(now),
            "task_name": script_name,
        },
        {
            "pattern": "C",
            "message": "Warning",
            "severity": "warning",
            "timestamp": alerts.format_timestamp(now - timedelta(days=2)),
            "task_name": script_name,
        },
    ]
    with open(alert_log, "w") as f:
        for a in alert_data:
            f.write(json.dumps(a) + "\n")
    # Prune to keep only last 5 days
    alerts.prune_alerts(script_name, max_days=5)
    with open(alert_log) as f:
        lines = f.readlines()
    # Only Info and Warning should remain (Critical is 10 days old)
    assert any("Info" in l for l in lines)
    assert any("Warning" in l for l in lines)
    assert not any("Critical" in l for l in lines)


def test_multiple_alerts_from_single_script(tmp_path, monkeypatch):
    """Test saving and loading multiple alerts from a single task."""
    script_name = "multi_script"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(alerts, "get_resolved_log_dir", lambda: str(log_dir))
    now = datetime.now()
    alerts_list = [
        {
            "pattern": "A",
            "message": "Alert 1",
            "severity": "info",
            "timestamp": alerts.format_timestamp(now),
            "task_name": script_name,
        },
        {
            "pattern": "B",
            "message": "Alert 2",
            "severity": "critical",
            "timestamp": alerts.format_timestamp(now),
            "task_name": script_name,
        },
    ]
    for alert in alerts_list:
        alerts.save_alert(script_name, alert)
    loaded = alerts.load_alerts(task_name=script_name)
    assert len(loaded) >= 2
    assert any(a["message"] == "Alert 1" for a in loaded)
    assert any(a["message"] == "Alert 2" for a in loaded)


def test_time_based_filtering_edge_cases(tmp_path, monkeypatch):
    """Test time-based filtering with future and ancient alerts."""
    script_name = "time_script"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(alerts, "get_resolved_log_dir", lambda: str(log_dir))
    alerts_dir = log_dir / script_name / "alerts"
    os.makedirs(alerts_dir)
    alert_log = alerts_dir / "alerts.jsonl"
    now = datetime.now()
    alert_data = [
        {
            "pattern": "A",
            "message": "Future",
            "severity": "info",
            "timestamp": alerts.format_timestamp(now + timedelta(days=365)),
            "task_name": script_name,
        },
        {
            "pattern": "B",
            "message": "Ancient",
            "severity": "info",
            "timestamp": alerts.format_timestamp(now - timedelta(days=365)),
            "task_name": script_name,
        },
    ]
    with open(alert_log, "w") as f:
        for a in alert_data:
            f.write(json.dumps(a) + "\n")
    # Only future alert should be returned for max_days=1
    recent = alerts.load_alerts(task_name=script_name, max_days=1)
    assert any("Future" in a["message"] for a in recent)
    assert not any("Ancient" in a["message"] for a in recent)


def test_load_alerts_filtering(tmp_path, monkeypatch):
    """Test loading alerts with various filters."""
    script_name = "test_script"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(alerts, "get_resolved_log_dir", lambda: str(log_dir))
    alerts_dir = log_dir / script_name / "alerts"
    os.makedirs(alerts_dir)
    alert_log = alerts_dir / "alerts.jsonl"
    now = datetime.now()
    # Write 3 alerts: critical, info, warning
    alert_data = [
        {
            "pattern": "A",
            "message": "Critical alert",
            "severity": "critical",
            "timestamp": alerts.format_timestamp(now),
            "task_name": script_name,
        },
        {
            "pattern": "B",
            "message": "Info alert",
            "severity": "info",
            "timestamp": alerts.format_timestamp(now - timedelta(days=2)),
            "task_name": script_name,
        },
        {
            "pattern": "C",
            "message": "Warning alert",
            "severity": "warning",
            "timestamp": alerts.format_timestamp(now - timedelta(days=1)),
            "task_name": script_name,
        },
    ]
    with open(alert_log, "w") as f:
        for a in alert_data:
            f.write(json.dumps(a) + "\n")
    # Filter by severity
    crit_alerts = alerts.load_alerts(task_name=script_name, severity="critical")
    assert len(crit_alerts) == 1
    assert crit_alerts[0]["severity"] == "critical"
    # Filter by days (only critical was written "now", others are 1-2 days old)
    recent_alerts = alerts.load_alerts(task_name=script_name, max_days=0)
    # max_days=0 means cutoff is now, so all alerts with timestamp < now are excluded
    # (at minimum, the ancient ones are excluded)
    # Filter by task
    task_alerts = alerts.load_alerts(task_name=script_name)
    assert len(task_alerts) == 3


def test_check_alert_patterns_empty(monkeypatch):
    script_name = "s"
    script_config = {}
    output = "no match"
    assert alerts.check_alert_patterns(script_name, script_config, output) == []


def test_check_alert_patterns_no_pattern(monkeypatch):
    script_name = "s"
    script_config = {"alerts": [{"message": "msg"}]}
    output = "anything"
    assert alerts.check_alert_patterns(script_name, script_config, output) == []


def test_check_alert_patterns_regex(monkeypatch):
    script_name = "s"
    script_config = {"alerts": [{"pattern": "\\d+", "message": "number found"}]}
    output = "value 123"
    result = alerts.check_alert_patterns(script_name, script_config, output)
    assert result and result[0]["message"] == "number found"


def test_save_and_load_alert(tmp_path, monkeypatch):
    script_name = "s"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(alerts, "get_resolved_log_dir", lambda: str(log_dir))
    alert = {
        "pattern": "p",
        "message": "m",
        "severity": "info",
        "timestamp": alerts.format_timestamp(datetime.now()),
        "task_name": script_name,
    }
    alerts.save_alert(script_name, alert)
    loaded = alerts.load_alerts(task_name=script_name)
    assert loaded and loaded[0]["message"] == "m"


def test_alert_retention(tmp_path, monkeypatch):
    """Pruning drops alerts older than max_days."""
    script_name = "test_script"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(alerts, "get_resolved_log_dir", lambda: str(log_dir))
    alerts_dir = log_dir / script_name / "alerts"
    alerts_dir.mkdir(parents=True)
    alert_log = alerts_dir / "alerts.jsonl"
    now = datetime.now()
    old_alert = {
        "severity": "critical",
        "timestamp": alerts.format_timestamp(now - timedelta(days=10)),
        "task_name": script_name,
    }
    new_alert = {"severity": "critical", "timestamp": alerts.format_timestamp(now), "task_name": script_name}
    with open(alert_log, "w") as f:
        f.write(json.dumps(old_alert) + "\n")
        f.write(json.dumps(new_alert) + "\n")
    # Prune to keep only alerts from last 5 days
    alerts.prune_alerts(script_name, max_days=5)
    with open(alert_log) as f:
        lines = f.readlines()
    assert len(lines) == 1


def test_prune_waits_for_a_concurrent_writer(tmp_path, monkeypatch):
    """Pruning must not rewrite the log while another run holds the lock, or that run's alert is lost."""
    import fcntl
    import threading

    monkeypatch.setattr(alerts, "get_resolved_log_dir", lambda: str(tmp_path))
    now = alerts.format_timestamp(datetime.now())
    alerts.save_alert("t", {"pattern": "a", "severity": "info", "timestamp": now})

    lock_path = tmp_path / "t" / "alerts" / ".alerts.lock"
    with open(lock_path, "w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        pruner = threading.Thread(target=alerts.prune_alerts, args=("t",), kwargs={"max_days": 30})
        pruner.start()
        pruner.join(timeout=0.3)
        assert pruner.is_alive()  # blocked on the lock
        # The "other run" appends while holding the lock
        with open(tmp_path / "t" / "alerts" / "alerts.jsonl", "a") as f:
            f.write(json.dumps({"pattern": "b", "severity": "info", "timestamp": now}) + "\n")
    pruner.join(timeout=5)

    assert sorted(a["pattern"] for a in alerts.load_alerts("t")) == ["a", "b"]


def test_clear_waits_for_a_concurrent_prune(tmp_path, monkeypatch):
    """Clearing must wait for the lock, or a prune in progress writes the old alerts back."""
    import fcntl
    import threading

    monkeypatch.setattr(alerts, "get_resolved_log_dir", lambda: str(tmp_path))
    alerts.save_alert("t", {"pattern": "a", "severity": "info", "timestamp": alerts.format_timestamp(datetime.now())})

    with open(tmp_path / "t" / "alerts" / ".alerts.lock", "w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        clearer = threading.Thread(target=alerts.clear_alerts, args=("t",))
        clearer.start()
        clearer.join(timeout=0.3)
        assert clearer.is_alive()  # blocked on the lock
    clearer.join(timeout=5)

    assert alerts.load_alerts("t") == []
