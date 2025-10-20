# signalbox 🚦

**Script execution control and monitoring**

signalbox is a CLI tool for managing, executing, and monitoring scripts with detailed logging, scheduling, and group execution capabilities. Like a railway signal box controls trains with signals and switches, signalbox controls your scripts with precision and reliability.

## Features

- 📋 List scripts and their last run status
- ▶️ Run individual scripts, groups, or all scripts
- 📊 View logs and execution history
- 🗂️ Organize scripts into logical groups
- ⚡ Parallel or serial execution modes
- 🛑 Stop-on-error for critical workflows
- ⏰ Schedule groups with cron expressions
- 🔄 Automatic log rotation (by count or age)
- 🔧 Generate systemd/cron configurations
- ✅ Configuration validation
- ⚙️ Customizable global settings
- 🌍 Language agnostic - works with any executable

## Why "signalbox"? 🚦

A railway signal box is a control center that:
- **Controls switches** to route trains (like routing scripts to execution)
- **Manages signals** to start/stop trains safely (like monitoring script success/failure)
- **Prevents conflicts** through interlocking (like handling dependencies)
- **Monitors all activity** from a central location (like centralized logging)

signalbox brings this same organized, safe, monitored approach to script execution.

## Installation
1. Install Python 3.8+
2. `pip install -r requirements.txt`
3. Run `python main.py --help`

## Quick Start

```bash
# List all scripts
python main.py list

# Run a single script
python main.py run hello

# Run a group of scripts
python main.py run-group system

# View latest log
python main.py logs hello

# List scheduled groups
python main.py list-schedules

# Validate configuration
python main.py validate

# View global settings
python main.py show-config
```

**Configuration Files:**
- `config.yaml` - Global settings and defaults (see [documentation/CONFIG_GUIDE.md](documentation/CONFIG_GUIDE.md))
- `scripts.yaml` or `scripts/` - Script definitions (what to run) - supports single file or directory
- `groups.yaml` - Groups and scheduling (when to run)
- See [documentation/FILE_STRUCTURE.md](documentation/FILE_STRUCTURE.md) for detailed examples

## Commands

### Script Management
- `list` - Show all scripts with status and last run time
- `run <name>` - Execute a specific script
- `run-all` - Execute all scripts sequentially
- `run-group <name>` - Execute all scripts in a group

### Group Management
- `list-groups` - Show all groups and their scripts
- `list-schedules` - Show scheduled groups with cron expressions

### Log Management
- `logs <name>` - View the latest log for a script
- `history <name>` - List all historical runs for a script
- `clear-logs <name>` - Clear logs for a specific script
- `clear-all-logs` - Clear all logs for all scripts

### Configuration Management
- `show-config` - Display all global configuration settings
- `get-setting <key>` - Get a specific config value (e.g., `execution.default_timeout`)
- `validate` - Validate configuration files

### Automation & Scheduling
- `export-systemd <group>` - Generate systemd service/timer files
- `export-cron <group>` - Generate crontab entry

## Configuration

### File Structure

Configuration is split into three separate files for better organization:

- **`config.yaml`** - Global settings and defaults (see [documentation/CONFIG_GUIDE.md](documentation/CONFIG_GUIDE.md))
- **`scripts.yaml`** - Defines all available scripts
- **`groups.yaml`** - Defines script groups and scheduling

**Benefits:**
- Clear separation of concerns
- Global config for timeouts, logging, and display preferences
- Scripts file contains execution details
- Groups file contains organization and scheduling
- Easier to maintain and version control

### Scripts File (`scripts.yaml`)

```yaml
scripts:
  - name: hello
    command: echo "Hello World"
    description: Simple echo script
    log_limit:
      type: count
      value: 5
  
  - name: backup
    command: /usr/local/bin/backup.sh
    description: Backup database
    log_limit:
      type: age
      value: 7
```

### Groups File (`groups.yaml`)

```yaml
groups:
  - name: daily
    description: Daily maintenance tasks
    schedule: "0 2 * * *"  # 2 AM daily
    scripts:
      - backup
      - cleanup
  
  - name: monitoring
    description: System monitoring
    schedule: "*/5 * * * *"  # Every 5 minutes
    scripts:
      - cpu_check
      - disk_check
```

### Legacy Support

For backwards compatibility, a single `config.yaml` file is still supported. If `scripts.yaml` and `groups.yaml` don't exist, the app will fall back to `config.yaml`.

### Migrating from Single Config

If you have an existing `config.yaml`, you can split it into separate files:

```bash
# 1. Create scripts.yaml with just the scripts section
cat config.yaml | grep -A 1000 "^scripts:" | grep -B 1000 "^groups:" | head -n -1 > scripts.yaml

# 2. Create groups.yaml with just the groups section  
cat config.yaml | grep -A 1000 "^groups:" > groups.yaml

# 3. Validate the new files
python main.py validate

# 4. Optional: Backup and remove old config.yaml
mv config.yaml config.yaml.backup
```

Or manually split the file:
1. Copy the `scripts:` section to `scripts.yaml`
2. Copy the `groups:` section to `groups.yaml`
3. Run `python main.py validate` to verify

### Scripts Configuration

Each script requires:
- `name` - Unique identifier
- `command` - Shell command to execute
- `description` - Human-readable description

Optional fields:
- `log_limit` - Log rotation configuration
  - `type: count` - Keep N most recent logs
  - `type: age` - Keep logs for N days

### Groups Configuration

Groups organize scripts into logical collections:
- `name` - Unique group identifier
- `description` - Purpose of the group
- `scripts` - List of script names
- `schedule` - (Optional) Cron expression for automation

## Scheduling Architecture

### Design Philosophy: Group-Only Scheduling

This tool uses a **group-only scheduling** approach, which means:

1. **Schedules are defined at the group level, not individual scripts**
2. **All automation happens through groups**
3. **Single scripts that need scheduling get their own group**

### Why Group-Only?

**Benefits:**
- ✅ **Single source of truth** - All schedules in one place
- ✅ **Clear organization** - Groups represent scheduling cadence ("daily", "hourly")
- ✅ **Less redundancy** - One schedule for multiple related scripts
- ✅ **Easier maintenance** - Update one schedule affects all group scripts
- ✅ **Simpler mental model** - Schedules are organizational units

**Alternatives considered:**
- ❌ Individual script scheduling - Leads to config bloat
- ❌ Hybrid approach - Confusing priority/override rules

### Singleton Groups Pattern

For individual scripts needing unique schedules, use **singleton groups**:

```yaml
groups:
  # Regular multi-script group
  - name: system-monitoring
    description: System health checks
    schedule: "*/5 * * * *"  # Every 5 minutes
    scripts:
      - cpu_check
      - disk_check
      - memory_check

  # Singleton group for one critical script
  - name: critical-backup-schedule
    description: Critical backup every 15 minutes
    schedule: "*/15 * * * *"
    scripts:
      - critical_backup  # Just one script
```

**Singleton groups are:**
- Named descriptively to indicate their purpose
- Used for scripts requiring special timing
- Still groups architecturally (consistent with design)
- Easy to understand and maintain

### Scheduling Examples

```yaml
groups:
  # Every 5 minutes
  - name: monitoring
    schedule: "*/5 * * * *"
    scripts: [cpu, disk, memory]
  
  # Hourly at minute 0
  - name: hourly-tasks
    schedule: "0 * * * *"
    scripts: [log_rotate, temp_cleanup]
  
  # Daily at 2 AM
  - name: daily
    schedule: "0 2 * * *"
    scripts: [backup, reports]
  
  # Weekly on Sunday at 3 AM
  - name: weekly
    schedule: "0 3 * * 0"
    scripts: [full_backup, audit]
  
  # Every 15 minutes (singleton pattern)
  - name: critical-sync
    schedule: "*/15 * * * *"
    scripts: [sync_critical_data]
```

## Automation Setup

### Option 1: systemd (Linux - Recommended)

Generate systemd files for a scheduled group:

```bash
# Generate files (creates systemd/<group>/ directory)
python main.py export-systemd daily

# Install (requires root)
sudo cp systemd/daily/signalbox-daily.service systemd/daily/signalbox-daily.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable signalbox-daily.timer
sudo systemctl start signalbox-daily.timer

# Check status
sudo systemctl status signalbox-daily.timer
```

**Note:** Files are exported to `systemd/<group_name>/` directory for better organization.

For user-level (no root):
```bash
python main.py export-systemd daily --user
```

### Option 2: cron (Universal)

Generate crontab entry:

```bash
# Generate entry (creates cron/<group>/ directory)
python main.py export-cron daily

# Add to crontab
crontab -e
# Paste the generated line
```

### Option 3: launchd (macOS)

For macOS, convert the systemd approach to launchd plist format, or use cron.

## Validation

Before deploying schedules, validate your configuration:

```bash
python main.py validate
```

This checks for:
- Missing required fields
- Duplicate names
- Non-existent script references
- Invalid cron syntax
- Configuration errors

## Log Rotation

Logs are automatically rotated based on `log_limit` configuration:

### By Count
```yaml
log_limit:
  type: count
  value: 5  # Keep 5 most recent logs
```

### By Age
```yaml
log_limit:
  type: age
  value: 7  # Keep logs for 7 days
```

## Documentation

Comprehensive guides are available in the `documentation/` directory:

- **[Configuration Guide](documentation/CONFIG_GUIDE.md)** - How to configure global settings, scripts, and groups
- **[Writing Scripts Guide](documentation/WRITING_SCRIPTS.md)** - Best practices for writing scripts that work with signalbox
- **[File Structure](documentation/FILE_STRUCTURE.md)** - Understanding the project layout and multi-file organization
- **[Config Reference](documentation/CONFIG_REFERENCE.md)** - Complete reference of all configuration options
- **[Config System](documentation/CONFIG_SYSTEM.md)** - Overview of the three-file configuration system
- **[Execution Modes](documentation/EXECUTION_MODES.md)** - Parallel vs serial execution explained
- **[Scheduling Examples](documentation/SCHEDULING_EXAMPLES.md)** - Real-world scheduling patterns and examples

## Architecture Decisions

### Why Not Individual Script Scheduling?

We evaluated three approaches:

1. **Groups-Only** ✅ (Chosen)
   - Clean, organized, easy to understand
   - Natural fit for scheduling cadences
   - Uses singleton pattern for edge cases

2. **Individual Scripts** ❌ (Rejected)
   - Config becomes bloated with redundant schedules
   - Harder to maintain and understand
   - Many similar schedules across scripts

3. **Hybrid** ❌ (Rejected)
   - Confusing priority rules (script vs group schedule)
   - Two places to define schedules
   - Inconsistent mental model

### Singleton Groups Best Practices

When a script needs a unique schedule:
1. Create a dedicated group
2. Name it descriptively: `<purpose>-schedule` or `<script>-every-<interval>`
3. Document why it needs special timing
4. Keep it in the groups section (architectural consistency)

Example:
```yaml
# DON'T: Inline schedule on script
scripts:
  - name: critical_backup
    schedule: "*/15 * * * *"  # Don't do this

# DO: Singleton group
groups:
  - name: critical-backup-every-15min
    description: Critical backup needs frequent execution
    schedule: "*/15 * * * *"
    scripts: [critical_backup]
```

## Troubleshooting

### Scripts not running via scheduler
- Check systemd timer status: `systemctl status signalbox-<group>.timer`
- View logs: `journalctl -u signalbox-<group>.service`
- Verify cron is running: `sudo systemctl status cron`
- Check crontab: `crontab -l`

### Configuration errors
- Run `python main.py validate` to check for issues
- Verify YAML syntax
- Ensure script names match between scripts and groups

### Logs not rotating
- Check `log_limit` configuration in script definition
- Verify log directory exists and is writable
- Run script manually to test rotation

## Examples

See `config.yaml` for a complete example with:
- Scripts with various commands
- Multiple groups
- Scheduled and unscheduled groups
- Singleton group pattern
- Different log rotation strategies

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

When adding features:
1. Maintain group-only scheduling architecture
2. Document any new patterns in README
3. Update `validate` command for new fields
4. Add tests for configuration validation

## License

MIT License - See [LICENSE](LICENSE) file for details

Copyright (c) 2025 Patrick Beard