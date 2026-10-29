# Configuration System Summary

## Configuration Files

### 1. `signalbox.yaml` - Global Settings
The default settings and the global options.
**Documentation**: refer to [CONFIG_GUIDE.md](CONFIG_GUIDE.md)

### 2. `tasks/*.yaml` - Task Definitions
These files tell signalbox which tasks are available and how to run them.

**Use these files to**:
  - Add new tasks

**Documentation**: refer to [FILE_STRUCTURE.md](FILE_STRUCTURE.md)

### 3. `groups/*.yaml` - Groups and Scheduling
These files put tasks into groups and tell when the groups run.

**Use these files to**:
- Make new groups
- Put tasks into groups
- Set schedules
- Make cron and systemd files for scheduled groups

**Documentation**: refer to [FILE_STRUCTURE.md](FILE_STRUCTURE.md) and [SCHEDULING_EXAMPLES.md](SCHEDULING_EXAMPLES.md)


## Configuration Commands

### View Configuration

```bash
# Show all global settings
signalbox config show

# Get a specific setting
# See Reference Table
signalbox config show execution.default_timeout

# Get nested objects
signalbox config show execution
```

### Validate Configuration

```bash
# Check all config files for errors
signalbox validate
```

The validate command does these checks:
- It examines `signalbox.yaml` for incorrect values.
- It examines `tasks/*.yaml` for necessary fields, safe names, time limits and alert patterns.
- It examines the structure of `groups/*.yaml`, and the tasks that each group refers to.
- It shows a warning for tasks that are not in a group. To stop this warning, set `validation.warn_unused_tasks: false`.
- It shows a summary of the global configuration.


## Further Reading

- [CONFIG_GUIDE.md](CONFIG_GUIDE.md): a full guide with examples
- [FILE_STRUCTURE.md](FILE_STRUCTURE.md): the format of task files and group files
- [SCHEDULING_EXAMPLES.md](SCHEDULING_EXAMPLES.md): examples of schedules


## Reference Table

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `default_log_limit.type` | string | count | The rule to delete old logs: `count`, `age` or `size` |
| `default_log_limit.value` | number | 10 | The number of logs, days or MB to keep (as the type tells) |
| `paths.log_dir` | string | logs | The directory for log files |
| `paths.tasks_file` | string | config/tasks | The directory of task YAML files |
| `paths.groups_file` | string | config/groups | The directory of group YAML files |
| `include_catalog` | boolean | false | Also load the example tasks and groups in `config/catalog/` |
| `paths.systemd_export_dir` | string | systemd | The directory for exported systemd files (relative to the signalbox home) |
| `paths.cron_export_dir` | string | cron | The directory for exported cron files (relative to the signalbox home) |
| `alerts.notifications.cooldown_minutes` | number | 60 | Do not send the same notification again (same task and alert pattern) in this number of minutes. 0 sends it on each run. |
| `tray.notify_on_success` | boolean | false | Show a tray message when a run that you started from the tray is successful |
| `execution.default_timeout` | number | 300 | The time limit of a task, in seconds. 0 removes the time limit. |
| `execution.min_timeout` | number | 1 | The smallest time limit, in seconds. Signalbox increases a lower value (except 0) to this value. |
| `execution.capture_stdout` | boolean | true | Write stdout to the logs |
| `execution.capture_stderr` | boolean | true | Write stderr to the logs |
| `execution.max_parallel_workers` | number | 5 | The maximum number of tasks that run at the same time in a parallel group |
| `logging.timestamp_format` | string | %Y%m%d_%H%M%S_%f | The timestamp in log filenames |
| `logging.max_file_size_mb` | number | 5 | The maximum size of one log file, in MB |
| `logging.include_command` | boolean | true | Write the command in the log |
| `logging.include_return_code` | boolean | true | Write the exit code in the log |
| `validation.strict` | boolean | false | Treat warnings as errors |
| `validation.warn_unused_tasks` | boolean | true | Show a warning for tasks that are not in a group |
| `display.colors` | boolean | true | Use colors in the terminal output |
| `display.include_paths` | boolean | false | Show the full file paths |
| `display.date_format` | string | %Y-%m-%d %H:%M:%S | The format of dates in the output |

For the alert settings, the group notification settings and the tray settings, refer to [NOTIFICATIONS.md](NOTIFICATIONS.md) and [TRAY_USAGE.md](TRAY_USAGE.md).
