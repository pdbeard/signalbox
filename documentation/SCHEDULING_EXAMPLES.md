# Scheduling Examples

This document gives examples of schedules. In signalbox, only groups can have a schedule.

## Basic Patterns

### Groups With More Than One Task
A group can run related tasks on the same schedule:

```yaml
groups:
  # Daily maintenance at 2 AM
  - name: daily-maintenance
    description: Daily cleanup and backup tasks
    schedule: "0 2 * * *"
    tasks:
      - cleanup_temp
      - rotate_logs
      - backup_database
      - generate_reports

```

### ❌ Do not add a schedule to a task. Add it to a group. A group can have only one task.

To give one task its own schedule, make a group for that task:
```yaml
# WRONG - Don't do this
tasks:
  - name: backup
    command: /backup.sh
    schedule: "*/15 * * * *" 
```

```yaml
# Correct
groups:
  - name: backup-group
    description: Backup every 15 minutes
    schedule: "*/15 * * * *"
    tasks:
      - backup
```

## Common Schedule Patterns

```yaml
groups:
  # Every minute
  - name: critical-checks
    schedule: "* * * * *"
    
  # Every 5 minutes
  - name: frequent-tasks
    schedule: "*/5 * * * *"
    
  # Every 15 minutes
  - name: regular-tasks
    schedule: "*/15 * * * *"
    
  # Every 30 minutes
  - name: semi-hourly
    schedule: "*/30 * * * *"
    
  # Hourly at minute 0
  - name: hourly-tasks
    schedule: "0 * * * *"
    
  # Daily at 2 AM
  - name: daily-tasks
    schedule: "0 2 * * *"
    
  # Weekly on Monday at 3 AM
  - name: weekly-tasks
    schedule: "0 3 * * 1"
    
  # Monthly on the 1st at 4 AM
  - name: monthly-tasks
    schedule: "0 4 1 * *"
    
  # Business hours only (9 AM - 5 PM, Mon-Fri)
  - name: business-hours-checks
    schedule: "0 9-17 * * 1-5"
```

## Tips for Organizing Schedules

1. **Make groups by frequency**: for example, "daily", "hourly" and "weekly".
2. **Make groups by purpose**: for example, "monitoring", "backups" and "maintenance".
3. **Give clear names to groups with one task**: put the time in the name, for example `backup-15min`.
4. **Tell why a group has only one task**: write the reason for the special time in the description.
5. **Keep related tasks together**: do not put related tasks in different groups.

## Deployment

After you add a `schedule` to the groups in `config/groups/*.yaml`, do these steps:

```bash
# Validate configuration
signalbox validate

# List all schedules
signalbox list-schedules

# Generate systemd files for each scheduled group
# (the cron schedule is converted to OnCalendar; files go to <signalbox home>/systemd/<group>/)
signalbox export-systemd monitoring
signalbox export-systemd daily-maintenance
signalbox export-systemd critical-backup-15min

# Or generate crontab entries (written to <signalbox home>/cron/<group>/<group>.cron)
signalbox export-cron monitoring
signalbox export-cron daily-maintenance
crontab -l > my-crontab
cat ~/.config/signalbox/cron/monitoring/monitoring.cron >> my-crontab
cat ~/.config/signalbox/cron/daily-maintenance/daily-maintenance.cron >> my-crontab
crontab my-crontab
```
