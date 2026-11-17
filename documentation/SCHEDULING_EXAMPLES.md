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

### Schedule Groups, Not Tasks

Only groups can have a schedule. To give one task its own schedule, make a group that has only that task:
```yaml
# Incorrect: a task cannot have a schedule
tasks:
  - name: backup
    command: /backup.sh
    schedule: "*/15 * * * *" 
```

```yaml
# Correct: a group with one task
groups:
  - name: backup-group
    description: Backup every 15 minutes
    schedule: "*/15 * * * *"
    tasks:
      - backup
```

## Common Schedule Patterns

Put one of these values in the `schedule` field of a group:

| Schedule | When the group runs |
|----------|---------------------|
| `"* * * * *"` | Every minute |
| `"*/5 * * * *"` | Every 5 minutes |
| `"*/15 * * * *"` | Every 15 minutes |
| `"*/30 * * * *"` | Every 30 minutes |
| `"0 * * * *"` | Every hour, at minute 0 |
| `"0 2 * * *"` | Every day at 2 AM |
| `"0 3 * * 1"` | Every Monday at 3 AM |
| `"0 4 1 * *"` | On the first day of each month at 4 AM |
| `"0 9-17 * * 1-5"` | Every hour from 9 AM to 5 PM, Monday to Friday |
| `"@daily"` | Every day at midnight (also `@hourly`, `@weekly`, `@monthly`, `@yearly`) |

`signalbox validate` examines each schedule the same way as cron. Each field must be in its range (for example, minute 0-59).

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
# The timer has Persistent=true: a start missed while the computer was off runs when it is on again
signalbox export-systemd monitoring
signalbox export-systemd daily-maintenance
signalbox export-systemd critical-backup-15min

# Or generate crontab entries (written to <signalbox home>/cron/<group>/<group>.cron)
# and add them to your crontab. Run it again after you change a schedule: the old line is replaced.
signalbox export-cron monitoring --install
signalbox export-cron daily-maintenance --install

# Check that every scheduled group ran when it was due (exit 0 OK, 1 overdue, 2 failed)
signalbox status
```
