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
tasks:
  - name: check_disk_space
    description: Monitor disk usage and warn if > 80%
    command: |
      echo 'Checking disk space...'
      df -h / | awk 'NR==2 { usage = $5; gsub(/%/, "", usage); if(usage > 80) print "ALERT: Disk usage HIGH: " usage "% (/ " $4 " free)"; else print "Disk usage OK: " usage "% (/ " $4 " free)" }'
    alerts:
      - pattern: "ALERT: Disk usage HIGH"
        title: "Disk Space Alert"
        message: "Disk usage is above 80%!"
        severity: critical
      - pattern: "Disk usage OK"
        title: "Disk Space Check"
        message: "Disk usage is normal."
        severity: info
        notify: false          # Per-alert override: don't send notifications
        on_failure_only: false # Per-alert override
```

## Alert Configuration Fields

- **`pattern`** (required): String or regex to match in script output
- **`message`** (required): The notification text shown to the user
- **`severity`** (optional): `info`, `warning`, `critical` (default: `info`)
- **`title`** (optional): Custom notification title (default: `"Alert: {task_name}"`)
- **`notify`** (optional): Override global `alerts.notifications.enabled` setting
- **`on_failure_only`** (optional): Override global `alerts.notifications.on_failure_only` setting

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

$ signalbox alerts check_disk_space --severity critical
[2026-01-15 14:05] [critical] check_disk_space: Disk usage is above 80%!
```

## Open Questions
- Should alerts be deduplicated or grouped?
- How long should alert history be retained?
- What notification channels are most useful for users?

## Configuration (Implemented)

### Global Configuration in signalbox.yaml

```yaml
alerts:
  # Alert retention policy
  retention:
    max_days: 30           # Keep alerts for 30 days
    max_entries: 1000      # Keep at most 1000 alerts per task
    per_severity:
      critical: 90         # Keep critical alerts for 90 days
      warning: 30          # Keep warning alerts for 30 days
      info: 7              # Keep info alerts for 7 days
  
  # Alert notification settings (when task output matches alert patterns)
  notifications:
    enabled: true          # Enable/disable alert notifications globally
    on_failure_only: true  # Only send notifications for critical/warning alerts (not info)
                           # Can be overridden per-alert with "notify" or "on_failure_only" fields

# Group notification settings (summary notifications after running groups)
group_notifications:
  enabled: true            # Enable/disable group execution summary notifications
  on_failure_only: true    # Only send notifications when tasks in the group fail
  show_failed_names: true  # Include failed task names in notifications
```

### Per-Alert Overrides

You can override notification settings for individual alerts:

```yaml
tasks:
  - name: my_task
    alerts:
      # This info alert will send notifications (overriding global on_failure_only)
      - pattern: "Success"
        message: "Task completed successfully"
        severity: info
        title: "Task Success"
        notify: true           # Force notification
        on_failure_only: false # Always notify
      
      # This critical alert won't send notifications
      - pattern: "ERROR"
        message: "Critical error detected"
        severity: critical
        notify: false  # Disable notification (still logged to console and storage)
```

**Override precedence:**
1. Per-alert setting (`notify`, `on_failure_only`) - highest priority
2. Global setting (`alerts.notifications.*`) - fallback

## Implementation Status

### ✅ Completed (v1)

1. **Alert Pattern Matching**
   - Tasks can define multiple alert conditions using regex patterns
   - Alerts are checked after task execution against stdout/stderr output

2. **Alert Storage**
   - Alerts are stored in `logs/<task_name>/alerts/alerts.jsonl`
   - Each alert includes: pattern, message, severity, title, timestamp, task name

3. **Alert Notifications**
   - Integrated with existing `notifications.py` module
   - Global configuration via `alerts.notifications` in signalbox.yaml
   - Per-alert overrides with `notify` and `on_failure_only` fields
   - Custom notification titles with `title` field

4. **Retention Policy**
   - Configurable retention by days, entry count, and per-severity
   - Automatic pruning of old alerts

5. **CLI Command**
   - `signalbox alerts` - List recent alerts
   - Filtering by task name and severity

6. **Notification Types**
   - **Alert notifications**: When task output matches alert patterns
   - **Group notifications**: Summary after running groups of tasks
   - Clear separation in configuration (alerts vs group_notifications)

### 🔄 Future Enhancements

- Alert deduplication and grouping
- Additional notification channels (email, Slack, webhooks)
- Alert suppression rules
- Alert escalation based on repeated occurrences
- Web dashboard for alert history
- Alert acknowledgment system

---
This design doc reflects the implemented alert system in Signalbox. Feedback and suggestions for future enhancements are welcome.
