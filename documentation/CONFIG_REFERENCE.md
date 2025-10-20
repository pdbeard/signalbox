# Global Configuration Options Reference

This is a complete reference of all settings available in `config.yaml`.

## Quick Reference

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

## Detailed Settings

### Log Rotation (`default_log_limit`)

Controls how many old log files are kept. Individual scripts can override in `scripts.yaml`.

**By count:**
```yaml
default_log_limit:
  type: count
  value: 10  # Keep last 10 log files
```

**By size:**
```yaml
default_log_limit:
  type: size
  value: 100  # Keep up to 100MB of logs
```

### Paths (`paths`)

Configure where files are located. Paths can be absolute or relative to the project directory.

```yaml
paths:
  log_dir: /var/log/script-monitor        # Absolute
  scripts_file: config/scripts.yaml        # Relative
  groups_file: config/groups.yaml
  systemd_export_dir: systemd              # Where to export systemd files
  cron_export_dir: cron                    # Where to export cron files
```

**Export directories:**
- `systemd_export_dir` - Base directory for systemd exports (creates `<dir>/<group>/` subdirectories)
- `cron_export_dir` - Base directory for cron exports (creates `<dir>/<group>/` subdirectories)

**Example structure:**
```
systemd/
  ├── daily/
  │   ├── script-monitor-daily.service
  │   └── script-monitor-daily.timer
  └── system/
      ├── script-monitor-system.service
      └── script-monitor-system.timer

cron/
  ├── daily/
  │   └── daily.cron
  └── system/
      └── system.cron
```

### Execution Settings (`execution`)

#### Timeout (`default_timeout`)

Maximum seconds a script can run. Set to 0 for no timeout.

```yaml
execution:
  default_timeout: 300  # 5 minutes
```

**Used by**: `run`, `run-all`, `run-group` commands

#### Output Capture

Control what gets logged:

```yaml
execution:
  capture_stdout: true   # Include standard output
  capture_stderr: true   # Include error output
```

**Used by**: `run_script()` function

#### Error Handling (`continue_on_error`)

**Note:** This setting is deprecated. Use group-level `stop_on_error` in `groups.yaml` instead.

When running groups or all scripts, determines if execution stops on first error:

```yaml
execution:
  continue_on_error: true   # Keep going (default)
  continue_on_error: false  # Stop on first failure
```

**Used by**: `run-all` command

**Better approach:** Set `stop_on_error` per group in `groups.yaml`:
```yaml
groups:
  - name: deployment
    execution: serial
    stop_on_error: true  # Stop this group on errors
```

#### Parallel Execution (`max_parallel_workers`)

Maximum number of scripts that can run simultaneously in parallel execution mode:

```yaml
execution:
  max_parallel_workers: 5  # Run up to 5 scripts at once
```

**Used by**: `run-group` command when `execution: parallel` is set in the group

**Considerations:**
- Higher values = more concurrent scripts (faster but more resource-intensive)
- Lower values = fewer concurrent scripts (slower but more controlled)
- System resources (CPU, memory) may limit practical max
- Default of 5 is suitable for most use cases

**Example:**
```yaml
# config.yaml
execution:
  max_parallel_workers: 10

# groups.yaml
groups:
  - name: monitoring
    execution: parallel  # Uses max_parallel_workers setting
    scripts:
      - check_service_1
      - check_service_2
      # ... up to 10 will run simultaneously
```

### Notifications (`notifications`)

*Future feature - not currently implemented*

```yaml
notifications:
  enabled: false
```

### Scheduling (`scheduling`)

#### Timezone

Determines when cron schedules run:

```yaml
scheduling:
  timezone: America/New_York  # Eastern time
  timezone: Europe/London      # UK time
  timezone: UTC                # Universal (default)
```

**Used by**: `export-systemd`, `export-cron` commands

#### Enable/Disable

Master switch for scheduling features:

```yaml
scheduling:
  enabled: true   # Scheduling commands work
  enabled: false  # Scheduling commands disabled
```

**Affects**: `list-schedules`, `export-systemd`, `export-cron`

### Logging Settings (`logging`)

#### Timestamp Format (`timestamp_format`)

Format for log filenames. Uses Python strftime codes.

```yaml
logging:
  timestamp_format: "%Y%m%d_%H%M%S_%f"  # 20231231_143059_123456
```

**Common formats:**
- `%Y%m%d_%H%M%S_%f` - 20231231_143059_123456 (default, includes microseconds)
- `%Y-%m-%d_%H-%M-%S` - 2023-12-31_14-30-59
- `%Y%m%d_%H%M%S` - 20231231_143059

**Used by**: `run_script()` function when creating log files

#### Log Content (`include_command`, `include_return_code`)

Control what metadata appears in logs:

```yaml
logging:
  include_command: true       # Show executed command
  include_return_code: true   # Show exit code
```

**Example log with both enabled:**
```
Command: echo "Hello"
Return code: 0
STDOUT:
Hello
```

**Example with both disabled:**
```
STDOUT:
Hello
```

**Used by**: `run_script()` function

### Validation Settings (`validation`)

#### Strict Mode (`strict`)

Treat warnings as errors during validation:

```yaml
validation:
  strict: false  # Warnings don't fail (default)
  strict: true   # Warnings cause failure
```

**Used by**: `validate` command

#### Warning Controls

Choose which warnings to show:

```yaml
validation:
  warn_unused_scripts: true  # Warn about scripts not in any group
  warn_empty_groups: true    # Warn about groups with no scripts
```

**Used by**: `validate` command

### Display Settings (`display`)

#### Colors (`use_colors`)

Enable/disable colored terminal output:

```yaml
display:
  use_colors: true   # Colorize (default)
  use_colors: false  # Plain text
```

**Affects**: `logs` command (colors log levels)

**Color scheme:**
- Green: Success messages, exit code 0
- Red: Error messages, non-zero exit codes
- Blue: Start messages

#### Full Paths (`show_full_paths`)

Show complete file paths in output:

```yaml
display:
  show_full_paths: true   # /full/path/to/logs/script/file.log
  show_full_paths: false  # Just show names (default)
```

**Affects**: `logs`, `history` commands

#### Date Format (`date_format`)

Format for displaying dates in terminal output:

```yaml
display:
  date_format: "%Y-%m-%d %H:%M:%S"  # 2023-12-31 14:30:59
```

**Common formats:**
- `%Y-%m-%d %H:%M:%S` - 2023-12-31 14:30:59 (default)
- `%m/%d/%Y %I:%M %p` - 12/31/2023 02:30 PM
- `%Y-%m-%d` - 2023-12-31
- `%B %d, %Y` - December 31, 2023

**Used by**: `history` command

## Accessing Config Values

### From Command Line

```bash
# View entire config
python main.py show-config

# Get specific value
python main.py get-setting execution.default_timeout
python main.py get-setting display.use_colors
```

### From Code

```python
# Load all global config
config = load_global_config()

# Get specific value with default
timeout = get_config_value('execution.default_timeout', 300)
use_colors = get_config_value('display.use_colors', True)
```

## Configuration Precedence

1. **Individual script settings** (in `scripts.yaml`) - highest priority
2. **Global config** (in `config.yaml`)
3. **Hardcoded defaults** - lowest priority

Example:
```yaml
# config.yaml
default_log_limit:
  type: count
  value: 10

# scripts.yaml
scripts:
  - name: special
    command: echo "test"
    log_limit:
      type: count
      value: 100  # This overrides the global default
```

## Best Practices

1. **Use strict mode in CI/CD**: Catch all issues during builds
2. **Disable colors in production**: Better for log aggregation
3. **Set appropriate timeouts**: Balance between hanging and legitimate long runs
4. **Keep log limits reasonable**: Prevent disk space issues
5. **Use absolute paths in production**: Avoid ambiguity
6. **Document custom settings**: Add comments in your config.yaml

## Example Configurations

See [CONFIG_GUIDE.md](CONFIG_GUIDE.md) for complete examples of:
- Development environment config
- Production environment config
- CI/CD environment config
- Environment-specific config management
