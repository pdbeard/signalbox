# Configuration File Structure

This document gives the directories and files that signalbox uses.

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

Signalbox keeps its configuration in **directories**. Thus, you can put tasks and groups in different files:

### **Tasks Directory** (`config/tasks/`)
This directory has the YAML files that define the tasks.
 - Signalbox loads all `.yaml` and `.yml` files in the directory, in alphabetical sequence. It does not load files that start with a dot.
 - Signalbox puts the tasks from all files into one list.

### **Groups Directory** (`config/groups/`)
This directory has the YAML files that define the groups and their schedules.
- Signalbox loads all `.yaml` and `.yml` files in the directory, in alphabetical sequence. It does not load files that start with a dot.
- Signalbox puts the groups from all files into one list.

### **Global Config** (`config/signalbox.yaml`)
One file that has the global settings, for example time limits, log limits and paths.

## Task Format

**Fields:**
- `name` (necessary): a name that no other task uses. Use only letters, digits, `_`, `-` and `.`. Do not start the name with `.` or `-`.
- `description` (necessary): a short description for people
- `command` (necessary): the shell command to run
- `timeout` (optional): the time limit in seconds. After this time, signalbox stops the task and all processes that it started. 0 removes the time limit.
- `cwd` (optional): the working directory. Use an absolute path, or a path relative to the signalbox home. The default is the signalbox home.
- `log_limit` (optional): the rule to delete old logs: `{type: count|age|size, value: N}`
- `alerts` (optional): the regular expressions to find in the output

**Note:** the sequence of the fields in YAML is not important. Signalbox keeps the run status (`last_run`, `last_status`) in `runtime/`. It never writes it in your configuration files.

## Group Format

**Fields:**
- `name` (necessary): a name that no other group uses (the same rules as task names)
- `description` (necessary): the purpose of the group
- `tasks` (necessary): a list of task names
- `schedule` (optional): a cron expression for automatic runs
- `execution` (optional): the execution mode, `serial` (the default) or `parallel`
- `stop_on_error` (optional): for serial groups only. If true, signalbox stops the group when a task fails. The default is false.
