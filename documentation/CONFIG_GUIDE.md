# Global Configuration Guide

The `config.yaml` file contains global settings that affect how signalbox operates. This file is separate from your scripts and groups configuration.

## Configuration Structure

```yaml
default_log_limit:
  type: count      # 'count' or 'size'
  value: 10        # Number of logs or size in MB

paths:
  log_dir: logs                  # Where to store log files
  scripts_file: scripts.yaml     # Path to scripts file OR directory
  groups_file: groups.yaml       # Path to groups configuration

execution:
  default_timeout: 300           # Script timeout in seconds (0 = no timeout)
  capture_stdout: true           # Capture standard output in logs
  capture_stderr: true           # Capture standard error in logs
  continue_on_error: true        # Continue executing other scripts if one fails

notifications:
  enabled: false                 # Enable email/webhook notifications (future)

scheduling:
  timezone: UTC                  # Timezone for cron schedules
  enabled: true                  # Enable/disable scheduling features

logging:
  timestamp_format: '%Y%m%d_%H%M%S_%f'  # Format for log filenames
  include_command: true          # Include executed command in logs
  include_return_code: true      # Include return code in logs

validation:
  strict: false                  # Fail validation on warnings
  warn_unused_scripts: true      # Warn about scripts not in any group
  warn_empty_groups: true        # Warn about groups with no scripts

display:
  use_colors: true               # Use colored output in terminal
  show_full_paths: false         # Show full file paths in output
  date_format: '%Y-%m-%d %H:%M:%S'  # Format for displaying dates
```

## Key Settings

### Default Log Limit

Controls how many log files are kept for each script:

```yaml
default_log_limit:
  type: count    # Keep last N log files
  value: 10
```

Or limit by size:

```yaml
default_log_limit:
  type: size     # Keep logs up to N MB
  value: 100
```

Individual scripts can override this in `scripts.yaml`.

### Execution Settings

**Timeout**: Maximum seconds a script can run before being killed:
```yaml
execution:
  default_timeout: 300  # 5 minutes
  # default_timeout: 0  # No timeout
```

**Continue on Error**: Whether to keep running other scripts if one fails:
```yaml
execution:
  continue_on_error: true  # Keep going
  # continue_on_error: false  # Stop on first error
```

### Path Configuration

Customize where files are located:

```yaml
paths:
  log_dir: /var/log/script-monitor   # Absolute path
  scripts_file: config/scripts.yaml   # Single file (relative to project root)
  # OR
  scripts_file: config/scripts        # Directory of .yaml files
  groups_file: config/groups.yaml
```

**Directory Mode Benefits:**
- Organize scripts into logical files (`web_servers.yaml`, `databases.yaml`, etc.)
- Better for large projects with many scripts
- Scripts automatically load from all `.yaml`/`.yml` files in directory
- Updates save back to original file (new scripts → `_new.yaml`)

See [FILE_STRUCTURE.md](FILE_STRUCTURE.md) for directory organization examples.

### Validation Modes

**Strict Mode**: Treats warnings as errors:
```yaml
validation:
  strict: true  # Fail on warnings
```

**Warning Controls**: Choose which warnings to show:
```yaml
validation:
  warn_unused_scripts: false  # Don't warn about unused scripts
  warn_empty_groups: false    # Don't warn about empty groups
```

### Display Options

**Colors**: Disable colors for CI/CD environments:
```yaml
display:
  use_colors: false  # Plain text output
```

**Date Format**: Customize how dates appear in `history` command:
```yaml
display:
  date_format: '%m/%d/%Y %I:%M %p'  # 12/31/2023 02:30 PM
```

**Full Paths**: Show complete file paths in output:
```yaml
display:
  show_full_paths: true  # Show /full/path/to/logs
```

## Viewing Configuration

### Show All Settings

```bash
python main.py show-config
```

### Get Specific Setting

```bash
python main.py get-setting execution.default_timeout
python main.py get-setting display.use_colors
python main.py get-setting paths.log_dir
```

Use dot notation to access nested values.

## Environment-Specific Configs

You can maintain different configs for different environments:

```bash
# Development
cp config.yaml config.dev.yaml

# Production
cp config.yaml config.prod.yaml
```

Then customize each file and use symbolic links:

```bash
# Switch to dev
ln -sf config.dev.yaml config.yaml

# Switch to prod
ln -sf config.prod.yaml config.yaml
```

## Common Scenarios

### Development Environment

```yaml
execution:
  default_timeout: 30  # Fail fast
  continue_on_error: false  # Stop on errors

logging:
  include_command: true
  include_return_code: true

display:
  use_colors: true
  show_full_paths: true  # Full debugging info

validation:
  strict: true  # Catch all issues
```

### Production Environment

```yaml
execution:
  default_timeout: 600  # Allow longer runs
  continue_on_error: true  # Keep services running

logging:
  include_command: true
  include_return_code: true

display:
  use_colors: false  # Plain logs for log aggregation
  show_full_paths: false

validation:
  strict: false  # Allow warnings
  warn_unused_scripts: false  # Don't care about unused scripts
```

### CI/CD Environment

```yaml
execution:
  default_timeout: 300
  continue_on_error: false  # Fail builds on errors

display:
  use_colors: false  # No ANSI codes in build logs
  show_full_paths: true  # Helpful for debugging

validation:
  strict: true  # Enforce quality
```

## Date/Time Formats

For `timestamp_format` (log filenames):
- `%Y%m%d_%H%M%S_%f` - 20231231_143059_123456
- `%Y-%m-%d_%H-%M-%S` - 2023-12-31_14-30-59

For `date_format` (display):
- `%Y-%m-%d %H:%M:%S` - 2023-12-31 14:30:59
- `%m/%d/%Y %I:%M %p` - 12/31/2023 02:30 PM
- `%Y-%m-%d` - 2023-12-31

See Python's `strftime()` documentation for all format codes.

## Timezone Configuration

For scheduled groups, the timezone determines when cron expressions run:

```yaml
scheduling:
  timezone: America/New_York  # EST/EDT
  # timezone: Europe/London   # GMT/BST
  # timezone: UTC             # Universal time
```

## Notes

- All paths can be absolute or relative to the project directory
- Boolean values: `true` or `false` (lowercase)
- Numbers don't need quotes: `timeout: 300` not `timeout: "300"`
- Strings with special characters need quotes: `format: "%Y-%m-%d"`
- Changes take effect immediately (no restart needed)
