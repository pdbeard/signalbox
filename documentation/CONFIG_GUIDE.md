# Global Configuration Guide

The `config/signalbox.yaml` file contains global settings that affect how signalbox operates. This file is separate from your scripts and groups configuration.

## Configuration Structure

```yaml
default_log_limit:
  type: count      # 'count' or 'age'
  value: 10        # Number of logs or days to keep

paths:
  log_dir: logs                  # Where to store log files
  scripts_file: config/scripts   # Path to scripts directory
  groups_file: config/groups     # Path to groups directory

execution:
  default_timeout: 300           # Script timeout in seconds (0 = no timeout)
  capture_stdout: true           # Capture standard output in logs
  capture_stderr: true           # Capture standard error in logs
  max_parallel_workers: 5        # Maximum parallel workers for group execution

logging:
  timestamp_format: '%Y%m%d_%H%M%S_%f'  # Format for log filenames

display:
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

Or limit by age:

```yaml
default_log_limit:
  type: age      # Keep logs for N days
  value: 7
```

Individual scripts can override this in their configuration.

### Execution Settings

**Timeout**: Maximum seconds a script can run before being killed:
```yaml
execution:
  default_timeout: 300  # 5 minutes
  # default_timeout: 0  # No timeout
```

**Output Capture**: Control what output is saved to logs:
```yaml
execution:
  capture_stdout: true   # Save standard output
  capture_stderr: true   # Save error output
```

**Parallel Workers**: Maximum concurrent workers for parallel group execution:
```yaml
execution:
  max_parallel_workers: 5  # Adjust based on system resources
```

### Path Configuration

Customize where files are located:

```yaml
paths:
  log_dir: logs                    # Directory for log files
  scripts_file: config/scripts     # Directory containing script YAML files
  groups_file: config/groups       # Directory containing group YAML files
```

- Scripts automatically load from all `.yaml`/`.yml` files in directory (and append accordingly)


See [FILE_STRUCTURE.md](FILE_STRUCTURE.md) for directory organization examples.


## Viewing Configuration

### Validate Configuration

```bash
python main.py validate
```

Shows configuration summary and validates all YAML files.

## Date/Time Formats

For `timestamp_format` (log filenames):
- `%Y%m%d_%H%M%S_%f` - 20231231_143059_123456
- `%Y-%m-%d_%H-%M-%S` - 2023-12-31_14-30-59

For `date_format` (display):
- `%Y-%m-%d %H:%M:%S` - 2023-12-31 14:30:59
- `%m/%d/%Y %I:%M %p` - 12/31/2023 02:30 PM
- `%Y-%m-%d` - 2023-12-31
- `%d %b %H:%M` - 31 Dec 14:30

See Python's `strftime()` documentation for all format codes.



