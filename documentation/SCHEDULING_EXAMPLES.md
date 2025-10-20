# Scheduling Examples

This document shows practical examples of the group-only scheduling architecture.

## Basic Patterns

### Multi-Script Groups (Standard Pattern)

Groups that run multiple related scripts on the same schedule:

```yaml
groups:
  # System monitoring every 5 minutes
  - name: monitoring
    description: System health checks
    schedule: "*/5 * * * *"
    scripts:
      - cpu_check
      - disk_check
      - memory_check
      - network_check

  # Daily maintenance at 2 AM
  - name: daily-maintenance
    description: Daily cleanup and backup tasks
    schedule: "0 2 * * *"
    scripts:
      - cleanup_temp
      - rotate_logs
      - backup_database
      - generate_reports

  # Hourly tasks
  - name: hourly-tasks
    description: Tasks that run every hour
    schedule: "0 * * * *"
    scripts:
      - check_services
      - update_metrics
      - send_heartbeat
```

### Singleton Groups (Edge Case Pattern)

When a single script needs a unique schedule, create a dedicated group:

```yaml
groups:
  # Critical backup every 15 minutes
  - name: critical-backup-15min
    description: Critical data backup (high frequency)
    schedule: "*/15 * * * *"
    scripts:
      - critical_database_backup

  # Certificate renewal check (daily at 3 AM)
  - name: ssl-cert-renewal
    description: Check and renew SSL certificates
    schedule: "0 3 * * *"
    scripts:
      - check_ssl_certs

  # Log shipping every 2 minutes
  - name: log-shipper
    description: Ship logs to central server
    schedule: "*/2 * * * *"
    scripts:
      - ship_application_logs
```

## Real-World Scenarios

### Scenario 1: Web Application Monitoring

```yaml
scripts:
  - name: check_http
    command: curl -f https://myapp.com/health
    description: HTTP health check
  
  - name: check_database
    command: /usr/local/bin/db-ping.sh
    description: Database connectivity check
  
  - name: check_disk
    command: df -h / | awk 'NR==2 {print $5}' | sed 's/%//' | awk '{if($1 > 90) exit 1}'
    description: Disk space check
  
  - name: restart_if_needed
    command: /usr/local/bin/auto-restart.sh
    description: Restart services if unhealthy

groups:
  # Frequent monitoring (every minute)
  - name: critical-monitoring
    description: Critical health checks
    schedule: "* * * * *"
    scripts:
      - check_http
      - check_database
  
  # Less frequent checks (every 5 minutes)
  - name: system-monitoring
    description: System resource checks
    schedule: "*/5 * * * *"
    scripts:
      - check_disk
  
  # Recovery actions (every 10 minutes)
  - name: auto-recovery
    description: Automatic recovery procedures
    schedule: "*/10 * * * *"
    scripts:
      - restart_if_needed
```

### Scenario 2: Data Pipeline

```yaml
scripts:
  - name: fetch_data
    command: python /opt/pipeline/fetch.py
    description: Fetch data from API
  
  - name: process_data
    command: python /opt/pipeline/process.py
    description: Process and transform data
  
  - name: load_data
    command: python /opt/pipeline/load.py
    description: Load data to warehouse
  
  - name: validate_data
    command: python /opt/pipeline/validate.py
    description: Validate data quality
  
  - name: send_notifications
    command: python /opt/pipeline/notify.py
    description: Send status notifications

groups:
  # Main pipeline runs hourly
  - name: data-pipeline
    description: Hourly data pipeline
    schedule: "0 * * * *"
    scripts:
      - fetch_data
      - process_data
      - load_data
      - validate_data
      - send_notifications
  
  # Critical data sync (singleton - every 15 minutes)
  - name: critical-data-sync
    description: High-priority data sync
    schedule: "*/15 * * * *"
    scripts:
      - fetch_data  # Only fetch, don't process
```

### Scenario 3: DevOps Automation

```yaml
scripts:
  - name: check_ssl
    command: /usr/local/bin/check-certs.sh
    description: Check SSL certificate expiration
  
  - name: renew_ssl
    command: certbot renew
    description: Renew SSL certificates
  
  - name: backup_configs
    command: /usr/local/bin/backup-configs.sh
    description: Backup configuration files
  
  - name: update_security
    command: apt-get update && apt-get upgrade -y
    description: Update system packages
  
  - name: clean_docker
    command: docker system prune -af
    description: Clean Docker resources

groups:
  # Daily SSL checks (singleton)
  - name: ssl-management
    description: Daily SSL certificate management
    schedule: "0 3 * * *"
    scripts:
      - check_ssl
      - renew_ssl
  
  # Weekly maintenance
  - name: weekly-maintenance
    description: Weekly system maintenance
    schedule: "0 4 * * 0"  # Sunday at 4 AM
    scripts:
      - backup_configs
      - update_security
      - clean_docker
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

## Anti-Patterns (Don't Do This)

### ❌ Don't: Add schedules to individual scripts

```yaml
# WRONG - Don't do this
scripts:
  - name: backup
    command: /backup.sh
    schedule: "0 2 * * *"  # Avoid inline schedules
```

### ✅ Do: Use singleton group instead

```yaml
# RIGHT - Use a group
groups:
  - name: backup-daily
    description: Daily backup at 2 AM
    schedule: "0 2 * * *"
    scripts:
      - backup
```

### ❌ Don't: Create overly generic singleton names

```yaml
# WRONG - Unclear purpose
groups:
  - name: script1-schedule
    schedule: "*/5 * * * *"
    scripts: [my_script]
```

### ✅ Do: Use descriptive singleton names

```yaml
# RIGHT - Clear purpose and timing
groups:
  - name: critical-sync-every-5min
    description: Critical data sync (high frequency required)
    schedule: "*/5 * * * *"
    scripts: [sync_critical_data]
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
