# Configuration System Summary

## Configuration Files

### 1. `signalbox.yaml` - Global Settings
Default settings and global options.
**Documentation**: See [CONFIG_GUIDE.md](CONFIG_GUIDE.md)

### 2. `scripts/*.yaml` - Script Definitions
Define what scripts are available and how to run them

**Summary**:
  - Add new scripts

**Documentation**: See [FILE_STRUCTURE.md](FILE_STRUCTURE.md)

### 3. `groups/*.yaml` - Groups and Scheduling
Organize scripts into groups and define when they run

**Summary**:
- Create new groups
- Assign scripts to groups
- Set up schedules
- Organise script execution (cron and systemd generation)

**Documentation**: See [FILE_STRUCTURE.md](FILE_STRUCTURE.md) and [SCHEDULING_EXAMPLES.md](SCHEDULING_EXAMPLES.md)


## Configuration Commands

### View Configuration

```bash
# Show all global settings
python signalbox.py show-config

# Get a specific setting
# See Reference Table
python signalbox.py get-setting execution.default_timeout 

# Get nested objects
python signalbox.py get-setting execution
```

### Validate Configuration

```bash
# Check all config files for errors
python signalbox.py validate
```

The validate command now:
- Checks `config.yaml` for valid values
- Validates `scripts/*.yaml` for required fields
- Validates `groups/*.yaml` structure and references
- Warns about unused scripts (configurable)
- Warns about empty groups (configurable)
- Shows summary with global config info


## Further Reading

- [CONFIG_GUIDE.md](CONFIG_GUIDE.md) - Comprehensive guide with examples
- [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md) - Complete reference of all settings
- [FILE_STRUCTURE.md](FILE_STRUCTURE.md) - Scripts and groups file format
- [SCHEDULING_EXAMPLES.md](SCHEDULING_EXAMPLES.md) - Scheduling patterns and examples




## Reference Table

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `default_log_limit.type` | string | count | Log rotation type: `count` or `size` |
| `default_log_limit.value` | number | 10 | Number of logs or MB |
| `paths.log_dir` | string | logs | Directory for log files |
| `paths.scripts_file` | string | scripts.yaml | Path to scripts config |
| `paths.groups_file` | string | groups.yaml | Path to groups config |
| `paths.systemd_export_dir` | string | systemd | Directory for exported systemd files |
| `paths.cron_export_dir` | string | cron | Directory for exported cron files |
| `execution.default_timeout` | number | 300 | Script timeout in seconds (0=none) |
| `execution.capture_stdout` | boolean | true | Capture stdout in logs |
| `execution.capture_stderr` | boolean | true | Capture stderr in logs |
| `execution.continue_on_error` | boolean | true | Keep running after failures (deprecated) |
| `execution.max_parallel_workers` | number | 5 | Max concurrent scripts in parallel mode |
| `notifications.enabled` | boolean | false | Enable notifications (future) |
| `scheduling.timezone` | string | UTC | Timezone for cron expressions |
| `scheduling.enabled` | boolean | true | Enable scheduling features |
| `logging.timestamp_format` | string | %Y%m%d_%H%M%S_%f | Log filename timestamp |
| `logging.include_command` | boolean | true | Show command in log |
| `logging.include_return_code` | boolean | true | Show exit code in log |
| `validation.strict` | boolean | false | Treat warnings as errors |
| `validation.warn_unused_scripts` | boolean | true | Warn about unused scripts |
| `validation.warn_empty_groups` | boolean | true | Warn about empty groups |
| `display.use_colors` | boolean | true | Colorize terminal output |
| `display.show_full_paths` | boolean | false | Show complete file paths |
| `display.date_format` | string | %Y-%m-%d %H:%M:%S | Display date format |