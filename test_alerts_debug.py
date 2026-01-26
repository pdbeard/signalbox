#!/usr/bin/env python3
from core.config import load_config
from core import alerts
import subprocess

config = load_config()
script = [s for s in config['scripts'] if s['name'] == 'check_dns_resolution'][0]

# Run the command
result = subprocess.run(script["command"], shell=True, capture_output=True, text=True, timeout=60)

# Get combined output
combined_output = result.stdout + "\n" + result.stderr

print("=== Debug Info ===")
print("STDOUT:", repr(result.stdout))
print("STDERR:", repr(result.stderr))
print("Combined:", repr(combined_output))
print("\n=== Checking Alerts ===")

triggered_alerts = alerts.check_alert_patterns('check_dns_resolution', script, combined_output)
print("Triggered alerts:", len(triggered_alerts))
for alert in triggered_alerts:
    print("Alert:", alert)
    
print("\n=== Saving Alerts ===")
if triggered_alerts:
    for alert in triggered_alerts:
        try:
            alerts.save_alert('check_dns_resolution', alert)
            print("Saved alert successfully")
        except Exception as e:
            print("Error saving alert:", e)
            import traceback
            traceback.print_exc()
else:
    print("No alerts triggered")
    
print("\n=== Checking Saved Alerts ===")
import os
alerts_dir = os.path.join("logs", "check_dns_resolution", "alerts")
if os.path.exists(alerts_dir):
    print("Alerts directory exists")
    alert_log = os.path.join(alerts_dir, "alerts.jsonl")
    if os.path.exists(alert_log):
        with open(alert_log) as f:
            lines = f.readlines()
            print(f"Found {len(lines)} alert(s)")
            for line in lines:
                print("  -", line.strip())
    else:
        print("No alerts.jsonl file found")
else:
    print("Alerts directory does not exist")
