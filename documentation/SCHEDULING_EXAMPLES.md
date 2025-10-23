# Scheduling Examples

This document shows practical examples of the group-only scheduling architecture.

## Basic Patterns

### Multi-Script Groups
Groups that run multiple related scripts on the same schedule:

```yaml
groups:
  # Daily maintenance at 2 AM
  - name: daily-maintenance
    description: Daily cleanup and backup tasks
    schedule: "0 2 * * *"
    scripts:
      - cleanup_temp
      - rotate_logs
      - backup_database
      - generate_reports

```

### ❌ Schedules can not be added to individual scripts, they must be added to a group. However, a group can consist of an individual script. 

When a single script needs a unique schedule, create a dedicated group:
```yaml
# WRONG - Don't do this
scripts:
  - name: backup
    command: /backup.sh
    schedule: "*/15 * * * *" 
```

```yaml
# Correct
groups:
  - name: backup-group
    description: 
    schedule: "*/15 * * * *"
    scripts:
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

1. **Group by cadence** - "daily", "hourly", "weekly" make sense
2. **Group by purpose** - "monitoring", "backups", "maintenance"
3. **Use descriptive singleton names** - Include timing in name for clarity
4. **Document why singletons exist** - Explain in description why special timing needed
5. **Keep related scripts together** - Don't split logically related tasks

## Deployment

After defining schedules in config.yaml:

```bash
# Validate configuration
python main.py validate

# List all schedules
python main.py list-schedules

# Generate systemd files for each scheduled group
python main.py export-systemd monitoring
python main.py export-systemd daily-maintenance
python main.py export-systemd critical-backup-15min

# Or generate crontab entries
python main.py export-cron monitoring >> my-crontab
python main.py export-cron daily-maintenance >> my-crontab
crontab my-crontab
```
