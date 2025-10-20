# Configuration System Summary

The script-monitor now uses a **three-file configuration system** for maximum flexibility and organization.

## Configuration Files

### 1. `config.yaml` - Global Settings
**Purpose**: Default settings and global options that affect how the tool operates

**What it contains**:
- Default log rotation limits
- File paths (log directory, config file locations)
- Execution settings (timeouts, error handling)
- Logging preferences (timestamp formats, what to include)
- Validation rules (strict mode, warnings)
- Display options (colors, date formats, path display)
- Scheduling defaults (timezone, enabled/disabled)

**When to edit**:
- Changing timeout defaults
- Customizing log retention
- Adjusting output formatting
- Setting up different environments (dev/prod/CI)

**Documentation**: See [CONFIG_GUIDE.md](CONFIG_GUIDE.md) and [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md)

### 2. `scripts.yaml` - Script Definitions
**Purpose**: Define what scripts are available and how to run them

**What it contains**:
- Script names and descriptions
- Commands to execute
- Individual log limits (optional, overrides global default)
- Last run status (auto-updated)

**When to edit**:
- Adding new scripts
- Modifying script commands
- Setting script-specific log limits
- Updating descriptions

**Documentation**: See [FILE_STRUCTURE.md](FILE_STRUCTURE.md)

### 3. `groups.yaml` - Groups and Scheduling
**Purpose**: Organize scripts and define when they run

**What it contains**:
- Group definitions
- Script membership (which scripts belong to which groups)
- Cron schedules (when groups should run)

**When to edit**:
- Creating new groups
- Assigning scripts to groups
- Setting up schedules
- Organizing script execution

**Documentation**: See [FILE_STRUCTURE.md](FILE_STRUCTURE.md) and [SCHEDULING_EXAMPLES.md](SCHEDULING_EXAMPLES.md)

## Architecture Benefits

### Separation of Concerns
- **Config**: How the tool behaves
- **Scripts**: What can be run
- **Groups**: When and how things are organized

### Flexibility
- Change global settings without touching script definitions
- Modify schedules without affecting script commands
- Override global defaults on a per-script basis

### Maintainability
- Each file has a clear, focused purpose
- Easy to find and modify specific settings
- Version control friendly (meaningful diffs)

### Environment Management
- Different `config.yaml` for dev/prod/CI
- Same `scripts.yaml` across environments
- Environment-specific `groups.yaml` for different schedules

## Configuration Commands

### View Configuration

```bash
# Show all global settings
python main.py show-config

# Get a specific setting
python main.py get-setting execution.default_timeout
python main.py get-setting display.use_colors
python main.py get-setting paths.log_dir

# Get nested objects
python main.py get-setting paths
python main.py get-setting validation
```

### Validate Configuration

```bash
# Check all config files for errors
python main.py validate
```

The validate command now:
- Checks `config.yaml` for valid values
- Validates `scripts.yaml` for required fields
- Validates `groups.yaml` structure and references
- Warns about unused scripts (configurable)
- Warns about empty groups (configurable)
- Shows summary with global config info

## How Settings Are Used

### Script Execution
When you run a script, the system:
1. Reads `execution.default_timeout` from `config.yaml`
2. Applies it unless the script has a specific timeout
3. Uses `logging.timestamp_format` to name the log file
4. Uses `logging.include_command` and `logging.include_return_code` to format log content
5. Saves to `paths.log_dir`
6. Rotates old logs using `default_log_limit` (or script-specific limit)

### Display Output
When showing information, the system:
1. Uses `display.use_colors` to colorize output
2. Uses `display.show_full_paths` to show/hide full file paths
3. Uses `display.date_format` for date display in `history` command

### Validation
When validating configuration:
1. Uses `validation.strict` to determine if warnings fail
2. Uses `validation.warn_unused_scripts` to check for orphaned scripts
3. Uses `validation.warn_empty_groups` to check for empty groups

## Configuration Precedence

Settings are applied in this order (highest to lowest priority):

1. **Script-specific settings** (in `scripts.yaml`)
   - Example: `log_limit` on individual script
   
2. **Global configuration** (in `config.yaml`)
   - Example: `default_log_limit`
   
3. **Hardcoded defaults** (in code)
   - Example: timeout defaults to 300 if not specified

## Quick Start Examples

### Example 1: Increase Timeout
```yaml
# config.yaml
execution:
  default_timeout: 600  # 10 minutes instead of 5
```

### Example 2: Disable Colors for CI
```yaml
# config.yaml
display:
  use_colors: false  # Plain text for build logs
```

### Example 3: Keep More Logs
```yaml
# config.yaml
default_log_limit:
  type: count
  value: 50  # Keep last 50 runs
```

### Example 4: Custom Log Directory
```yaml
# config.yaml
paths:
  log_dir: /var/log/script-monitor  # System logs directory
```

### Example 5: Strict Validation
```yaml
# config.yaml
validation:
  strict: true  # Warnings become errors
```

## Migration Guide

If you have an old single `config.yaml` with both scripts and groups:

1. **Backup** your current `config.yaml`
2. **Create** `scripts.yaml` with your script definitions
3. **Create** `groups.yaml` with your group definitions
4. **Update** `config.yaml` to only contain global settings (see template below)

### Template config.yaml

```yaml
# Global Configuration
default_log_limit:
  type: count
  value: 10

paths:
  log_dir: logs
  scripts_file: scripts.yaml
  groups_file: groups.yaml

execution:
  default_timeout: 300
  capture_stdout: true
  capture_stderr: true
  continue_on_error: true

logging:
  timestamp_format: "%Y%m%d_%H%M%S_%f"
  include_command: true
  include_return_code: true

validation:
  strict: false
  warn_unused_scripts: true
  warn_empty_groups: true

display:
  use_colors: true
  show_full_paths: false
  date_format: "%Y-%m-%d %H:%M:%S"
```

## Troubleshooting

### "Config file not found"
- Ensure `config.yaml` exists in the project root
- Check `paths.scripts_file` and `paths.groups_file` point to correct locations

### "Invalid config value"
- Run `python main.py validate` to check for errors
- Use `python main.py show-config` to see current values
- Check [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md) for valid options

### "Setting not taking effect"
- Verify syntax in `config.yaml` (proper YAML indentation)
- Check if script has override in `scripts.yaml`
- Use `python main.py get-setting <key>` to verify value

### "Colors not working"
- Check `display.use_colors: true` in config
- Some terminals don't support ANSI colors
- Try `python main.py logs <script>` to test

## Further Reading

- [CONFIG_GUIDE.md](CONFIG_GUIDE.md) - Comprehensive guide with examples
- [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md) - Complete reference of all settings
- [FILE_STRUCTURE.md](FILE_STRUCTURE.md) - Scripts and groups file format
- [SCHEDULING_EXAMPLES.md](SCHEDULING_EXAMPLES.md) - Scheduling patterns and examples
