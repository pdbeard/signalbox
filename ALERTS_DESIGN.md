# Signalbox Alerts Design Document

## Overview
The Signalbox Alerts feature enables users to receive actionable notifications based on script output, not just script success or failure. This allows for more granular monitoring and timely responses to important system events.

## Goals
- Allow scripts to define multiple alert conditions using output pattern matching.
- Provide a CLI command (`signalbox alerts`) to list recent alerts.
- Store alert history for querying and reporting.
- Support extensible alert types and notification channels.

## Key Concepts
- **Alert Pattern**: A string or regex to match in script output.
- **Alert Message**: The notification text shown to the user.
- **Alert Severity**: Optional field (info, warning, critical) for filtering and prioritization.
- **Alert Timestamp**: When the alert was triggered.
- **Script Association**: Each alert is linked to the script that triggered it.

## YAML Configuration Example
```yaml
scripts:
  - name: check_disk_space
    description: Monitor disk usage and warn if > 80%
    command: |
      echo 'Checking disk space...'
      df -h / | awk 'NR==2 { usage = $5; gsub(/%/, "", usage); if(usage > 80) print "ALERT: Disk usage HIGH: " usage "% (/ " $4 " free)"; else print "Disk usage OK: " usage "% (/ " $4 " free)" }'
    alerts:
      - pattern: "ALERT: Disk usage HIGH"
        message: "Disk usage is above 80%!"
        severity: critical
      - pattern: "Disk usage OK"
        message: "Disk usage is normal."
        severity: info
```

## Implementation Steps
1. **Extend Script YAML Schema**
   - Add `alerts` field (list of pattern/message/severity).
2. **Script Execution**
   - After running a script, parse stdout for alert patterns.
   - For each match, create an alert record with details.
3. **Alert Storage**
   - Store alerts in a dedicated log file or lightweight database (e.g., SQLite, JSON).
   - Include script name, message, severity, timestamp, and output snippet.
4. **CLI Command: `signalbox alerts`**
   - List recent alerts with filtering options (by time, severity, script).
   - Show summary: script, message, timestamp, severity.
   - Support filtering by script name: `signalbox alerts <script_name>` shows alerts only for the specified script. If no script is given, show all alerts (default behavior).
5. **Notification Integration (Future)**
   - Optionally send alerts via email, Slack, etc.
   - Allow user-configurable notification channels.

## Extensibility
- Support regex patterns for advanced matching.
- Allow custom alert handlers (Python or shell scripts).
- Add alert suppression, escalation, and grouping features.

## Example CLI Output
```
$ signalbox alerts
[2026-01-15 14:05] [critical] check_disk_space: Disk usage is above 80%!
[2026-01-15 13:55] [info] check_disk_space: Disk usage is normal.
```

## Open Questions
- Should alerts be deduplicated or grouped?
- How long should alert history be retained?
- What notification channels are most useful for users?

## Configuration Suggestions
### v1 Configuration Approach

- **Retention Policy:**
   - Support both `max_days` (e.g., keep alerts for 30 days) and `max_entries` (e.g., keep last 1000 alerts).
   - Allow special cases for severity (e.g., keep critical alerts longer).
   - Example:
      ```yaml
      alerts:
         retention:
            max_days: 30
            max_entries: 1000
            per_severity:
               critical: 90
               warning: 30
               info: 7
      ```

- **Notification Settings:**
   - Simple enable/disable option at both global (signalbox.yaml) and local (script YAML) level.
   - Notifications will use the existing `notifications.py` module.
   - Example:
      ```yaml
      alerts:
         notifications:
            enabled: true
      ```

- **Storage:**
   - Store alert logs in a simple file-based structure, similar to existing logs and runtime data.
   - Alert logs can be placed in `logs/<script>/alerts`.

- **Filtering & Suppression:**
   - Filtering and suppression will be handled at the CLI level for v1 (e.g., `signalbox alerts --critical`, `signalbox alerts script-name --info`).

- **UI/GUI:**
   - No UI commands or controls for v1; focus is on CLI and config-driven management.

---
This design doc provides a foundation for implementing robust, user-driven alerts in Signalbox. Feedback and suggestions are welcome.

---

## Step-by-Step Implementation Plan (v1)

1. **Update Configuration Schema**
   - Add `alerts.retention` and `alerts.notifications.enabled` options to both global (signalbox.yaml) and local script YAML schemas.
   - Support `max_days`, `max_entries`, and `per_severity` for retention.

2. **Alert Logging Structure**
   - Create a directory structure for alert logs: `logs/<script>/alerts`.
   - Store each alert as a line or record (e.g., JSON or plain text) with timestamp, severity, message, and script name.

3. **Retention Enforcement**
   - On alert log write or periodically, prune old alerts based on `max_days`, `max_entries`, and `per_severity` settings.

4. **Notification Logic**
   - Check the `enabled` flag (global and local) before sending notifications.
   - Use the existing `notifications.py` module to send notifications for new alerts.

5. **CLI Filtering**
   - Update the `signalbox alerts` CLI to support filtering by severity (`--critical`, `--info`, etc.) and by script name (`signalbox alerts <script_name>`).

6. **Documentation**
   - Update user documentation and config guides to explain new alert retention and notification options.

7. **Testing**
   - Add tests for retention logic, notification enable/disable, and CLI filtering.

8. **Review and Iterate**
   - Gather feedback from users and refine retention, notification, and filtering features as needed.
