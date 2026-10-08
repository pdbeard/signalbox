# Configuration File Structure

This document explains the directory-based configuration system for signalbox.

## File Structure Overview

```
~/.config/signalbox/          # The signalbox home (or $SIGNALBOX_HOME / $XDG_CONFIG_HOME/signalbox)
├── config/
│   ├── signalbox.yaml        # Global configuration
│   ├── tasks/                # Task definitions: any number of *.yaml / *.yml files
│   ├── groups/               # Group definitions: any number of *.yaml / *.yml files
│   └── catalog/              # Example tasks/groups (loaded only with include_catalog: true)
├── logs/
│   └── <task>/
│       ├── <timestamp>.log   # One file per run
│       └── alerts/alerts.jsonl
├── runtime/                  # last_run / last_status state, written by signalbox
│   ├── tasks/
│   ├── groups/
│   └── tray_state.json
├── systemd/                  # Output of `signalbox export-systemd`
└── cron/                     # Output of `signalbox export-cron`
```

## Configuration System

signalbox uses **directory-based configuration** for easy organization:

### **Tasks Directory** (`config/tasks/`)
Contains YAML files defining tasks to execute.
 - All `.yaml` and `.yml` files in the directory are loaded (sorted alphabetically); dotfiles are skipped
 - Tasks from all files are combined into a single list

### **Groups Directory** (`config/groups/`)
Contains YAML files defining groups of tasks and scheduling.
- All `.yaml` and `.yml` files in the directory are loaded (sorted alphabetically); dotfiles are skipped
- Groups from all files are combined into a single list

### **Global Config** (`config/signalbox.yaml`)
Single file containing global settings like timeouts, log limits, and paths.

## Task Format

**Fields:**
- `name` (required) - Unique identifier; letters, digits, `_`, `-` and `.` only, not starting with `.` or `-`
- `description` (required) - Human-readable description
- `command` (required) - Shell command to execute
- `timeout` (optional) - Seconds before the task and everything it started are killed (0 = no timeout)
- `cwd` (optional) - Working directory, absolute or relative to the signalbox home (default: the signalbox home)
- `log_limit` (optional) - Log rotation: `{type: count|age|size, value: N}`
- `alerts` (optional) - Regex patterns to match in the output

**Note:** Field order in YAML doesn't affect functionality. Run state (`last_run`, `last_status`) is kept in `runtime/`, never in your config files.

## Group Format

**Fields:**
- `name` (required) - Unique identifier (same rules as task names)
- `description` (required) - Purpose of the group
- `tasks` (required) - List of task names
- `schedule` (optional) - Cron expression for automation
- `execution` (optional) - Execution mode: `serial` (default) or `parallel`
- `stop_on_error` (optional) - For serial execution only: stop if a task fails (default: false)
