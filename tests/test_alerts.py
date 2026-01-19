import os
import tempfile
import shutil
import pytest
from core import alerts
from datetime import datetime, timedelta

def test_check_alert_patterns_and_save(tmp_path, monkeypatch):
    # Setup: create a fake script config with alerts
    script_name = "test_script"
    script_config = {
        "alerts": [
            {"pattern": "ALERT: Disk usage HIGH", "message": "Disk usage is above 80%!", "severity": "critical"},
            {"pattern": "Disk usage OK", "message": "Disk usage is normal.", "severity": "info"}
        ]
    }
    output = "Checking disk space...\nALERT: Disk usage HIGH: 85% (/ 10G free)\n"

    # Patch get_config_value to use a temp log dir
    log_dir = tmp_path / "logs"
    monkeypatch.setattr(alerts, "get_config_value", lambda key, default=None: str(log_dir) if key == "paths.log_dir" else default)

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
    monkeypatch.setattr(alerts, "get_config_value", lambda key, default=None: str(log_dir) if key == "paths.log_dir" else default)
    alerts_dir = log_dir / script_name / "alerts"
    os.makedirs(alerts_dir)
    alert_log = alerts_dir / "alerts.jsonl"
    now = datetime.now()
    # Write 3 alerts: critical, info, warning
    alert_data = [
        {"pattern": "A", "message": "Critical alert", "severity": "critical", "timestamp": alerts.format_timestamp(now), "script_name": script_name},
        {"pattern": "B", "message": "Info alert", "severity": "info", "timestamp": alerts.format_timestamp(now - timedelta(days=2)), "script_name": script_name},
        {"pattern": "C", "message": "Warning alert", "severity": "warning", "timestamp": alerts.format_timestamp(now - timedelta(days=1)), "script_name": script_name},
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
    assert len(recent_alerts) == 2
    # Filter by script
    script_alerts = alerts.load_alerts(script_name=script_name)
    assert len(script_alerts) == 3
