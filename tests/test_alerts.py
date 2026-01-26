import os
from core import alerts
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

    # Patch get_config_value to use a temp log dir
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(
        alerts, "get_config_value", lambda key, default=None: str(log_dir) if key == "paths.log_dir" else default
    )

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


def test_load_alerts_filtering(tmp_path, monkeypatch):
    script_name = "test_script"
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(
        alerts, "get_config_value", lambda key, default=None: str(log_dir) if key == "paths.log_dir" else default
    )
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
            "script_name": script_name,
        },
        {
            "pattern": "B",
            "message": "Info alert",
            "severity": "info",
            "timestamp": alerts.format_timestamp(now - timedelta(days=2)),
            "script_name": script_name,
        },
        {
            "pattern": "C",
            "message": "Warning alert",
            "severity": "warning",
            "timestamp": alerts.format_timestamp(now - timedelta(days=1)),
            "script_name": script_name,
        },
    ]
    with open(alert_log, "w") as f:
        for a in alert_data:
            f.write(alerts.json.dumps(a) + "\n")
    # Load all
    all_alerts = alerts.load_alerts()
    assert len(all_alerts) == 3
    # Filter by severity
    crit_alerts = alerts.load_alerts(severity="critical")
    assert len(crit_alerts) == 1
    assert crit_alerts[0]["severity"] == "critical"
    # Filter by days
    recent_alerts = alerts.load_alerts(max_days=1)
    assert len(recent_alerts) == 1
    # Filter by script
    script_alerts = alerts.load_alerts(script_name=script_name)
    assert len(script_alerts) == 3

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
    monkeypatch.setattr(alerts, "get_config_value", lambda k, d=None: str(log_dir))
    alert = {"pattern": "p", "message": "m", "severity": "info", "timestamp": alerts.format_timestamp(datetime.now()), "script_name": script_name}
    alerts.save_alert(script_name, alert)
    loaded = alerts.load_alerts(script_name=script_name)
    assert loaded and loaded[0]["message"] == "m"

    def test_alert_retention_and_summary(tmp_path, monkeypatch):
        import json
        from datetime import datetime, timedelta
        script_name = "test_script"
        log_dir = tmp_path / "logs"
        monkeypatch.setattr(
            alerts, "get_config_value", lambda key, default=None: str(log_dir) if key == "paths.log_dir" else default
        )
        alerts_dir = log_dir / script_name / "alerts"
        alerts_dir.mkdir(parents=True)
        alert_log = alerts_dir / "alerts.jsonl"
        now = datetime.now()
        old_alert = {"severity": "critical", "timestamp": (now - timedelta(days=10)).isoformat(), "script_name": script_name}
        new_alert = {"severity": "critical", "timestamp": now.isoformat(), "script_name": script_name}
        with open(alert_log, "w") as f:
            f.write(json.dumps(old_alert) + "\n")
            f.write(json.dumps(new_alert) + "\n")
        # Retain only alerts from last 5 days
        alerts.retain_alerts(script_name, max_days=5)
        with open(alert_log) as f:
            lines = f.readlines()
        assert len(lines) == 1
        # Test summary
        monkeypatch.setattr(alerts, 'load_alerts', lambda: [new_alert])
        summary = alerts.get_alert_summary()
        assert summary['total'] == 1
        assert summary['by_severity']['critical'] == 1
        assert summary['by_script'][script_name] == 1
