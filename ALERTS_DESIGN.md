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

---
This design doc provides a foundation for implementing robust, user-driven alerts in Signalbox. Feedback and suggestions are welcome.
