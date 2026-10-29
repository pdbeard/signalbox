# Global Configuration Guide

The `config/signalbox.yaml` file has the global settings of signalbox. These settings apply to all tasks and groups. The task files and the group files are separate from this file.

## Configuration Location

Signalbox looks for its configuration in these locations, in this sequence:
1. **`$SIGNALBOX_HOME`**: the directory in this environment variable
2. **`$XDG_CONFIG_HOME/signalbox`**: used only if `XDG_CONFIG_HOME` has a value
3. **`~/.config/signalbox/`**: the user configuration directory. Use this location for a normal installation.
4. **The current working directory**: for development, or for the configuration of one project

This is an example for a normal installation:
```bash
# Make the configuration directory
signalbox init

# Or set a different location
export SIGNALBOX_HOME=/path/to/your/config
```

## Configuration Structure

```yaml
default_log_limit:
  type: count      # 'count', 'age' or 'size'
  value: 10        # Number of logs, days or MB to keep

paths:
  log_dir: logs                  # Where to store log files (relative to config home)
  tasks_file: config/tasks       # Path to tasks directory (relative to config home)
  groups_file: config/groups     # Path to groups directory (relative to config home)

execution:
  default_timeout: 300           # Task timeout in seconds (0 = no timeout)
  min_timeout: 1                 # Smallest timeout allowed (except 0)
  capture_stdout: true           # Capture standard output in logs
  capture_stderr: true           # Capture standard error in logs
  max_parallel_workers: 5        # Maximum parallel workers for group execution

logging:
  timestamp_format: '%Y%m%d_%H%M%S_%f'  # Format for log filenames
  max_file_size_mb: 5                   # Maximum size of one log file

display:
  date_format: '%Y-%m-%d %H:%M:%S'  # Format for displaying dates
```

**Note:** If a path in the configuration is not absolute, signalbox uses it relative to the configuration home. The configuration home is the directory that holds `config/signalbox.yaml`.

## Key Settings

### Default Log Limit

This setting tells signalbox which old logs of a task to delete:

```yaml
default_log_limit:
  type: count    # Keep last N log files
  value: 10
```

You can also use the age of the logs:

```yaml
default_log_limit:
  type: age      # Keep logs for N days
  value: 7
```

Or you can use the total size of the logs:

```yaml
default_log_limit:
  type: size     # Keep the newest logs that fit in N MB
  value: 50
```

A task can have its own `log_limit`. It replaces this setting for that task.

### Execution Settings

**Timeout**: the maximum time, in seconds, that a task can run. When the time is over, signalbox stops the task:
```yaml
execution:
  default_timeout: 300  # 5 minutes
  # default_timeout: 0  # No timeout
```

**Output capture**: these settings tell signalbox which output to write to the logs:
```yaml
execution:
  capture_stdout: true   # Save standard output
  capture_stderr: true   # Save error output
```

**Parallel workers**: the maximum number of tasks that run at the same time in a parallel group:
```yaml
execution:
  max_parallel_workers: 5  # Adjust based on system resources
```

### Path Configuration

These settings tell signalbox where the files are:

```yaml
paths:
  log_dir: logs                    # Directory for log files
  tasks_file: config/tasks         # Directory containing task YAML files
  groups_file: config/groups       # Directory containing group YAML files
```

- Signalbox loads the tasks from all `.yaml` and `.yml` files in the directory, and adds them to one list.

For examples of how to organize the directories, refer to [FILE_STRUCTURE.md](FILE_STRUCTURE.md).


## Viewing Configuration

### Validate Configuration

```bash
signalbox validate
```

This command examines all YAML files and shows a summary of the configuration.

## Date/Time Formats

For `timestamp_format` (log filenames):
- `%Y%m%d_%H%M%S_%f` - 20231231_143059_123456
- `%Y-%m-%d_%H-%M-%S` - 2023-12-31_14-30-59

For `date_format` (display):
- `%Y-%m-%d %H:%M:%S` - 2023-12-31 14:30:59
- `%m/%d/%Y %I:%M %p` - 12/31/2023 02:30 PM
- `%Y-%m-%d` - 2023-12-31
- `%d %b %H:%M` - 31 Dec 14:30

For all format codes, refer to the Python `strftime()` documentation.
