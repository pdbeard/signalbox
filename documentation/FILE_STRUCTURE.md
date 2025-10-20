# Configuration File Structure

This document explains the directory-based configuration system for signalbox.

## File Structure Overview

```
signalbox/
├── scripts/           # Script definitions directory
│   ├── basic.yaml     # Basic utility scripts
│   ├── system.yaml    # System monitoring scripts
│   └── test.yaml      # Test scripts
├── groups/            # Group definitions directory
│   ├── basic.yaml     # Basic groups (no schedule)
│   ├── scheduled.yaml # Scheduled groups
│   └── test.yaml      # Test groups
├── config.yaml        # Global configuration
├── main.py            # CLI application
└── logs/              # Execution logs
```

## Configuration System

signalbox uses **directory-based configuration** for easy organization:

### **Scripts Directory** (`scripts/`)
Contains YAML files defining scripts to execute. All `.yaml` and `.yml` files in this directory are automatically loaded.

### **Groups Directory** (`groups/`)
Contains YAML files defining groups of scripts and scheduling. All `.yaml` and `.yml` files in this directory are automatically loaded.

### **Global Config** (`config.yaml`)
Single file containing global settings like timeouts, log limits, and paths.
└── logs/              # Execution logs
```

## Scripts Directory Configuration

All scripts are defined in the `scripts/` directory. Each `.yaml` or `.yml` file in this directory defines scripts.

**config.yaml:**
```yaml
paths:
  scripts_file: scripts  # Directory containing script YAML files
```

**scripts/basic.yaml:**
```yaml
scripts:
  - name: hello
    description: Simple greeting
    command: echo "Hello"
  
  - name: show_date
    description: Show current date
    command: date
```

**scripts/system.yaml:**
```yaml
scripts:
  - name: disk_usage
    description: Show disk usage
    command: df -h
  
  - name: system_uptime
    description: Show system uptime
    command: uptime
```

**scripts/test.yaml:**
```yaml
scripts:
  - name: fail_test
    description: Test failure handling
    command: exit 1
```

### How It Works

1. **Loading**: All `.yaml` and `.yml` files in the directory are loaded (sorted alphabetically)
2. **Merging**: Scripts from all files are combined into a single list
3. **Saving**: Each script is saved back to its **original file**
   - If you run a script from `system.yaml`, updates go to `system.yaml`
   - New scripts created via CLI are saved to `_new.yaml`
4. **Organization**: Use filenames to logically group scripts:
   - `web_servers.yaml` - Web server monitoring
   - `databases.yaml` - Database scripts
   - `local_pc.yaml` - Local machine scripts
   - `deployments.yaml` - Deployment workflows

### Script Format

Defines **what** scripts exist and **how** they run:

```yaml
scripts:
  # Minimal script
  - name: hello
    command: echo "Hello"
    description: Simple greeting

  # Script with log rotation
  - name: backup
    command: /usr/local/bin/backup.sh
    description: Database backup
    log_limit:
      type: count
      value: 10

  # Script with age-based log cleanup
  - name: cleanup
    command: /usr/local/bin/cleanup.sh
    description: Temp file cleanup
    log_limit:
      type: age
      value: 7  # Keep logs for 7 days
```

**Fields:**
- `name` (required) - Unique identifier
- `description` (required) - Human-readable description
- `command` (required) - Shell command to execute
- `log_limit` (optional) - Log rotation configuration
- `last_run` (auto) - Last execution timestamp
- `last_status` (auto) - Last execution status

**Note:** Field order in YAML doesn't affect functionality, but the recommended order is:
1. `name` - identifier
2. `description` - what it does
3. `command` - how it runs
4. Optional fields (`log_limit`)
5. Auto-populated fields (`last_run`, `last_status`)

## Groups Directory Configuration

All groups are defined in the `groups/` directory. Each `.yaml` or `.yml` file in this directory defines groups.

**config.yaml:**
```yaml
paths:
  groups_file: groups  # Directory containing group YAML files
```

**groups/basic.yaml:**
```yaml
groups:
  - name: development
    description: Development utilities
    execution: parallel
    scripts:
      - hello
      - cleanup
```

**groups/scheduled.yaml:**
```yaml
groups:
  - name: monitoring
    description: System monitoring
    schedule: "*/5 * * * *"  # Every 5 minutes
    execution: parallel
    scripts:
      - cpu_check
      - disk_check
      - memory_check
  
  - name: daily
    description: Daily maintenance
    schedule: "0 2 * * *"  # 2 AM daily
    execution: serial
    stop_on_error: true
    scripts:
      - backup
      - cleanup
```

### How It Works

1. **Loading**: All `.yaml` and `.yml` files in the directory are loaded (sorted alphabetically)
2. **Merging**: Groups from all files are combined into a single list
3. **Saving**: Each group is saved back to its **original file**
   - Group configuration updates go back to their source file
   - New groups created via CLI are saved to `_new.yaml`
4. **Organization**: Use filenames to logically group:
   - `scheduled.yaml` - Groups with cron schedules
   - `manual.yaml` - On-demand execution groups
   - `production.yaml` - Production workflows
   - `development.yaml` - Dev/test groups

### Group Format

Defines **when** and **which** scripts to run:

```yaml
groups:
  # Unscheduled group (manual execution)
  - name: development
    description: Development utilities
    scripts:
      - hello
      - cleanup

  # Scheduled group (automated)
  - name: monitoring
    description: System monitoring
    schedule: "*/5 * * * *"  # Every 5 minutes
    scripts:
      - cpu_check
      - disk_check
      - memory_check

  # Parallel execution group (faster execution)
  - name: system_info
    description: Gather system information
    execution: parallel  # Run all scripts simultaneously
    scripts:
      - cpu_info
      - disk_info
      - memory_info

  # Serial execution with error handling
  - name: deployment
    description: Deploy application
    execution: serial  # Run scripts in order
    stop_on_error: true  # Stop if any script fails
    scripts:
      - pre_deploy_check
      - stop_app
      - update_code
      - start_app
      - post_deploy_test

  # Singleton group (one script, special schedule)
  - name: critical-backup-15min
    description: Critical backup every 15 minutes
    schedule: "*/15 * * * *"
    scripts:
      - critical_backup
```

**Fields:**
- `name` (required) - Unique identifier
- `description` (required) - Purpose of the group
- `scripts` (required) - List of script names
- `schedule` (optional) - Cron expression for automation
- `execution` (optional) - Execution mode: `serial` (default) or `parallel`
- `stop_on_error` (optional) - For serial execution only: stop if a script fails (default: false)

## Execution Modes

### Serial Execution (Default)

Scripts run **one at a time** in the order specified.

**Use when:**
- Scripts depend on each other (e.g., deployment pipeline)
- Order matters
- Scripts modify shared resources
- You need predictable execution order

**Example:**
```yaml
- name: deployment
  description: Deploy application
  execution: serial
  stop_on_error: true  # Stop if any step fails
  scripts:
    - run_tests
    - build_app
    - deploy_app
    - verify_deploy
```

**Behavior with `stop_on_error`:**
- `stop_on_error: true` - Stops at first failure (recommended for critical workflows)
- `stop_on_error: false` - Continues even if scripts fail (default)

### Parallel Execution

Scripts run **simultaneously** for faster completion.

**Use when:**
- Scripts are independent
- Speed is important
- Scripts don't share resources
- Monitoring multiple systems

**Example:**
```yaml
- name: monitoring
  description: Check all services
  execution: parallel
  scripts:
    - check_web_server
    - check_database
    - check_cache
    - check_queue
```

**Benefits:**
- **Faster**: 4 scripts that take 10s each complete in ~10s instead of 40s
- **Efficient**: Better resource utilization
- **Summary**: Shows success/failure counts at the end

**Note:** Parallel execution ignores `stop_on_error` since scripts run simultaneously.

**Configuration:**
Set max parallel workers in `config.yaml`:
```yaml
execution:
  max_parallel_workers: 5  # Max number of concurrent scripts
```

## Real-World Examples

### Example 1: Multi-Environment Setup

**scripts.yaml** (same across all environments):
```yaml
scripts:
  - name: health_check
    command: curl -f http://localhost/health
    description: Application health check
  
  - name: backup_db
    command: /usr/local/bin/backup-db.sh
    description: Database backup
```

**groups.yaml** (dev environment):
```yaml
groups:
  - name: monitoring
    description: Dev environment monitoring
    schedule: "*/10 * * * *"  # Every 10 minutes (less frequent)
    scripts:
      - health_check
```

**groups.yaml** (production environment):
```yaml
groups:
  - name: monitoring
    description: Production monitoring
    schedule: "* * * * *"  # Every minute (more frequent)
    scripts:
      - health_check
  
  - name: backups
    description: Production backups
    schedule: "0 */2 * * *"  # Every 2 hours
    scripts:
      - backup_db
```

### Example 2: Team Ownership

**scripts.yaml** (managed by development team):
```yaml
scripts:
  - name: deploy_app
    command: /opt/scripts/deploy.sh
    description: Deploy application
  
  - name: run_tests
    command: /opt/scripts/test.sh
    description: Run test suite
  
  - name: migrate_db
    command: /opt/scripts/migrate.sh
    description: Database migrations
```

**groups.yaml** (managed by operations team):
```yaml
groups:
  - name: ci-pipeline
    description: CI/CD pipeline
    scripts:
      - run_tests
      - migrate_db
      - deploy_app
  
  - name: nightly-deploy
    description: Nightly deployment
    schedule: "0 2 * * *"
    scripts:
      - run_tests
      - deploy_app
```

### Example 3: Modular Configuration

**scripts.yaml**:
```yaml
scripts:
  # Monitoring scripts
  - name: check_cpu
    command: top -bn1 | grep "Cpu(s)"
    description: CPU usage check
  
  - name: check_disk
    command: df -h
    description: Disk space check
  
  # Backup scripts
  - name: backup_files
    command: rsync -av /data /backup
    description: File backup
  
  - name: backup_database
    command: mysqldump mydb > /backup/db.sql
    description: Database backup
  
  # Maintenance scripts
  - name: cleanup_logs
    command: find /var/log -mtime +30 -delete
    description: Clean old logs
  
  - name: update_packages
    command: apt-get update && apt-get upgrade -y
    description: System updates
```

**groups.yaml**:
```yaml
groups:
  # Monitoring groups
  - name: monitoring-frequent
    description: Frequent system checks
    schedule: "*/5 * * * *"
    scripts:
      - check_cpu
      - check_disk
  
  # Backup groups
  - name: backup-hourly
    description: Hourly file backup
    schedule: "0 * * * *"
    scripts:
      - backup_files
  
  - name: backup-daily
    description: Daily database backup
    schedule: "0 2 * * *"
    scripts:
      - backup_database
  
  # Maintenance groups
  - name: maintenance-weekly
    description: Weekly maintenance
    schedule: "0 3 * * 0"  # Sunday 3 AM
    scripts:
      - cleanup_logs
      - update_packages
```

## Migration Guide

### From Single File to Dual Files

**Before (config.yaml):**
```yaml
scripts:
  - name: script1
    command: cmd1
    description: Description 1
  - name: script2
    command: cmd2
    description: Description 2

groups:
  - name: group1
    scripts: [script1, script2]
```

**After:**

**scripts.yaml:**
```yaml
scripts:
  - name: script1
    command: cmd1
    description: Description 1
  - name: script2
    command: cmd2
    description: Description 2
```

**groups.yaml:**
```yaml
groups:
  - name: group1
    scripts: [script1, script2]
```

### Automated Migration

```bash
# Option 1: Manual split
# Copy scripts section to scripts.yaml
# Copy groups section to groups.yaml

# Option 2: Using yq (if installed)
yq eval '.scripts' config.yaml > scripts.yaml
yq eval '.groups' config.yaml > groups.yaml

# Validate
python main.py validate

# Backup old file
mv config.yaml config.yaml.backup
```

## Best Practices

### DO ✅

1. **Keep scripts.yaml focused on execution**
   ```yaml
   scripts:
     - name: task1
       command: /path/to/script.sh
       description: What it does
       log_limit: ...
   ```

2. **Keep groups.yaml focused on organization**
   ```yaml
   groups:
     - name: scheduled-task
       description: When and why
       schedule: "0 2 * * *"
       scripts: [task1]
   ```

3. **Use descriptive names**
   - Scripts: `backup_database`, `check_ssl_certs`
   - Groups: `daily-backups`, `monitoring-critical`

4. **Document schedules in groups**
   ```yaml
   - name: hourly-checks
     description: Health checks run every hour
     schedule: "0 * * * *"
   ```

### DON'T ❌

1. **Don't put scheduling in scripts**
   ```yaml
   # WRONG - don't do this
   scripts:
     - name: backup
       schedule: "0 2 * * *"  # No schedule here!
   ```

2. **Don't duplicate script definitions**
   - Define each script once in scripts.yaml
   - Reference by name in groups.yaml

3. **Don't mix concerns**
   - Keep execution details out of groups.yaml
   - Keep scheduling out of scripts.yaml

## Advanced Patterns

### Shared Scripts, Different Schedules

**scripts.yaml:**
```yaml
scripts:
  - name: sync_data
    command: /usr/local/bin/sync.sh
    description: Data synchronization
```

**groups.yaml:**
```yaml
groups:
  # Frequent sync for critical data
  - name: critical-sync
    description: Critical data sync every 5 minutes
    schedule: "*/5 * * * *"
    scripts: [sync_data]
  
  # Less frequent sync for bulk data
  - name: bulk-sync
    description: Bulk data sync hourly
    schedule: "0 * * * *"
    scripts: [sync_data]
```

### Environment-Specific Groups

Use different groups.yaml per environment:

```bash
script-monitor/
├── scripts.yaml              # Common scripts
├── groups.dev.yaml          # Dev scheduling
├── groups.staging.yaml      # Staging scheduling
└── groups.prod.yaml         # Production scheduling
```

Symlink the appropriate file:
```bash
ln -s groups.prod.yaml groups.yaml
```

## Troubleshooting

### Scripts not found
- Check script names match between files
- Run `python main.py validate` to check references

### Changes not taking effect
- Scripts: Edits take effect immediately
- Groups: Automation configs need regeneration
  ```bash
  python main.py export-systemd <group>
  ```

### File conflicts
- If both config.yaml and scripts.yaml exist, scripts.yaml takes precedence
- Remove or rename config.yaml to avoid confusion

## Summary

| Aspect | scripts.yaml | groups.yaml |
|--------|-------------|-------------|
| Purpose | Define what runs | Define when/which |
| Managed by | Development | Operations |
| Changes affect | Script execution | Scheduling |
| Environment-specific | No (usually shared) | Yes (per environment) |
| Version control | Less frequent changes | More frequent changes |
| Dependencies | None | References scripts.yaml |
