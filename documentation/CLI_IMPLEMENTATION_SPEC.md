# CLI Implementation Specification v1.0
*Actionable specification for Signalbox CLI improvements - Ready for Implementation*

---

## Document Overview

This specification outlines CLI improvements divided into two clear sections:
- **V1 Release Scope**: Features to implement now for first official release
- **Future Enhancements**: Good ideas to revisit after v1 stabilizes

**Key Priorities for V1:**
1. **Terminology migration** (scripts → tasks) - HIGHEST PRIORITY
2. **XDG Base Directory support** - Bug fix, must be included
3. **Command restructuring** - Better organization with Click groups
4. **Log management suite** - `log list`, `log show`, `log tail`
5. **Exit code standardization** - Proper POSIX conventions

**Explicitly Excluded from V1:**
- Test fixes (deferred until features stabilize)
- `--dry-run` flags (low priority)
- Global `--quiet/--verbose` flags (low priority)
- `doctor` diagnostics command (future feature)
- Full task stats/analytics (v2 feature)

---

## V1 Release Scope

---

## Priority 1: Terminology Standardization (CRITICAL)

**Problem:** Inconsistent use of "scripts" vs "tasks" throughout codebase, user-facing strings, and documentation.

**Decision:** Full migration to **"tasks"** everywhere - no backward compatibility needed since no official release exists yet.

### Changes Required:

**1. User-Facing Strings (Start Here):**
- All CLI command help text: "run a script" → "run a task"
- All CLI output messages and prompts
- All error messages
- Documentation files (README, all guides in `documentation/`)
- Config template file `core/config/signalbox.yaml`
- Example YAML files

**2. Internal Function Names:**
- `save_script_runtime_state()` → `save_task_runtime_state()`
- `get_script_log_dir()` → `get_task_log_dir()`
- `clear_script_logs()` → `clear_task_logs()`
- `load_script_runtime_state()` → `load_task_runtime_state()`
- All variable names in functions (script → task, scripts → tasks)

**3. Config YAML Structure:**
- Support both `scripts` and `tasks` keys during transition
- Prefer `tasks` in all new configs and documentation
- No deprecation warnings needed (clean break for v1)

```python
# Config loader should accept both
tasks = config.get("tasks", config.get("scripts", {}))
```

**4. Directory Structure:**
- Runtime directory: `runtime/scripts/` → `runtime/tasks/`
- Update path references in all modules

**5. Test Files (when tests are addressed later):**
- All fixture names
- All mock data structures
- All assertion messages

### Implementation Order:
1. Rename all internal functions (`core/runtime.py`, `core/log_manager.py`, `core/executor.py`)
2. Update all function calls to use new names
3. Update all CLI command text and help strings
4. Update config loader to accept both keys
5. Update all documentation
6. Update directory paths and references
7. Verify with fresh `init` that templates use "tasks"

---

## Priority 2: XDG Base Directory Support (BUG FIX)

**Problem:** `init()` and `ConfigManager.find_config_home()` hardcode `~/.config/signalbox`, ignoring `XDG_CONFIG_HOME`.

**Solution:**
Update `ConfigManager.find_config_home()` to respect environment variables in this order:

1. `SIGNALBOX_HOME` (if set) - highest priority, explicit override
2. `XDG_CONFIG_HOME/signalbox` (if `XDG_CONFIG_HOME` is set)
3. `~/.config/signalbox` (default fallback)

**Implementation:**
```python
def find_config_home(self) -> str:
    """Find the configuration home directory."""
    # 1. Check explicit override
    if "SIGNALBOX_HOME" in os.environ:
        path = os.path.expanduser(os.environ["SIGNALBOX_HOME"])
        return path
    
    # 2. Check XDG_CONFIG_HOME
    if "XDG_CONFIG_HOME" in os.environ:
        xdg_config = os.path.expanduser(os.environ["XDG_CONFIG_HOME"])
        return os.path.join(xdg_config, "signalbox")
    
    # 3. Default to ~/.config/signalbox
    return os.path.expanduser("~/.config/signalbox")
```

**Files to Update:**
- `core/config.py::ConfigManager.find_config_home()`
- Verify `init()` command uses this method (don't hardcode paths)
- Update README to document environment variable behavior

**Testing:** Manual verification (tests deferred):
```bash
# Test 1: Default behavior
unset SIGNALBOX_HOME XDG_CONFIG_HOME
signalbox config path  # Should show ~/.config/signalbox

# Test 2: XDG_CONFIG_HOME
export XDG_CONFIG_HOME=~/custom_config
signalbox config path  # Should show ~/custom_config/signalbox

# Test 3: SIGNALBOX_HOME overrides XDG
export XDG_CONFIG_HOME=~/custom_config
export SIGNALBOX_HOME=~/my_signalbox
signalbox config path  # Should show ~/my_signalbox
```

---

## Priority 3: Exit Code Standardization


**Problem:** Current exit codes are inconsistent. Need standard POSIX-compliant codes while maintaining key feature: `run_all` continues through failures.

**Solution:** Use standard exit codes:
```
0   - Success (all tasks passed)
1   - Task execution failures (one or more tasks failed, but all were attempted)
2   - Command usage error (bad arguments, missing config, validation failure)
126 - Command found but not executable (permission issues)
130 - Terminated by Ctrl+C (SIGINT)
```

### Critical Behavior: `run_all` Must Continue

**User Requirement:** `run_all` must execute ALL tasks even if some fail, then return exit code 1 at the end if any failed.

**Current Behavior:** Runs all tasks but exits with code 0 even when tasks fail.

**Fixed Behavior:**
```python
@cli.command(name="run-all")  # or task run --all
def run_all():
    """Run all configured tasks."""
    tasks = config.get("tasks", {})
    failed_tasks = []
    
    for task_name, task_config in tasks.items():
        try:
            # Execute task
            result = execute_task(task_name, task_config)
            if not result.success:
                failed_tasks.append(task_name)
        except Exception as e:
            click.echo(f"Error running {task_name}: {e}", err=True)
            failed_tasks.append(task_name)
        # IMPORTANT: Continue to next task regardless of failure
    
    # All tasks attempted, now exit with appropriate code
    if failed_tasks:
        click.echo(f"\n{len(failed_tasks)} task(s) failed: {', '.join(failed_tasks)}", err=True)
        sys.exit(1)  # Exit 1 indicates failures occurred
    else:
        click.echo("\nAll tasks completed successfully")
        sys.exit(0)
```

### Validation Command Behavior

**User Requirement:** `validate` must return ALL errors found, not just exit on first error.

**Implementation:**
```python
@cli.command()
def validate():
    """Validate configuration files."""
    errors = []
    warnings = []
    
    # Collect all validation errors
    errors.extend(validate_yaml_structure())
    errors.extend(validate_task_commands())
    errors.extend(validate_group_references())
    warnings.extend(check_optional_fields())
    
    # Display all findings
    if warnings:
        click.echo("Warnings:", err=True)
        for warning in warnings:
            click.echo(f"  ⚠  {warning}", err=True)
    
    if errors:
        click.echo("\nErrors:", err=True)
        for error in errors:
            click.echo(f"  ✗  {error}", err=True)
        click.echo(f"\nValidation failed with {len(errors)} error(s)")
        sys.exit(2)  # Exit 2 for config/validation errors
    else:
        click.echo("✓ Configuration is valid")
        sys.exit(0)
```

### Exception Handler Updates

Update `handle_exceptions()` in `cli_commands.py`:

```python
def handle_exceptions(func):
    """Decorator to handle exceptions and return appropriate exit codes."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            click.echo("\nInterrupted by user", err=True)
            sys.exit(130)
        except ValidationError as e:
            click.echo(f"Validation Error: {e}", err=True)
            sys.exit(2)
        except ConfigError as e:
            click.echo(f"Configuration Error: {e}", err=True)
            sys.exit(2)
        except FileNotFoundError as e:
            click.echo(f"File Not Found: {e}", err=True)
            sys.exit(2)
        except PermissionError as e:
            click.echo(f"Permission Denied: {e}", err=True)
            sys.exit(126)
        except SignalboxError as e:
            # Task execution errors
            message = getattr(e, 'message', str(e))
            click.echo(f"Error: {message}", err=True)
            sys.exit(1)
        except Exception as e:
            click.echo(f"Unexpected error: {e}", err=True)
            if os.getenv("DEBUG"):
                import traceback
                traceback.print_exc()
            sys.exit(1)
    return wrapper
```

**Files to Update:**
- `core/cli_commands.py::run_all()` - track failures, exit 1 if any failed
- `core/cli_commands.py::validate()` - collect all errors before exiting
- `core/cli_commands.py::handle_exceptions()` - proper exit code mapping
- `core/exceptions.py` - ensure exception classes have proper attributes

**Documentation:**
Add to README:
```markdown
## Exit Codes

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Success | All tasks completed successfully |
| 1 | Task failures | One or more tasks failed execution |
| 2 | Usage error | Invalid config, bad arguments, validation failed |
| 126 | Permission denied | Cannot execute command due to permissions |
| 130 | Interrupted | User pressed Ctrl+C |
```

---

## Priority 4: Command Restructuring


**Problem:** Flat command structure (`run-group`, `list-groups`, `log-history`) is inconsistent and doesn't scale well.

**Solution:** Organize into logical command groups using Click's `@click.group()` feature.

### New Command Structure:

```
signalbox
├── task (group) - Task management commands
│   ├── run <name>               # Run a single task
│   ├── run --all                # Run all tasks (replaces run-all)
│   ├── list                     # List all configured tasks (name + description)
│   ├── info <name>              # Show full details for a specific task
│   └── search <query>           # Find tasks by name/description/command
│
├── group (group) - Group management commands
│   ├── run <name>               # Run a group (replaces run-group)
│   ├── list                     # List all configured groups
│   └── info <name>              # Show group details (tasks, settings)
│
├── log (group) - Log management commands
│   ├── list [OPTIONS]           # List all task runs with filters (NEW)
│   ├── show <task> [run_id]     # Display full log content (NEW)
│   ├── tail <task>              # Follow log in real-time (NEW)
│   ├── clear [--task NAME]      # Clear logs (replaces clear-logs)
│   └── stats                    # Log statistics (future)
│
├── config (group) - Configuration commands
│   ├── show [key]               # Display config or specific setting (NEW)
│   ├── validate                 # Validate configuration
│   └── path                     # Print config directory path (NEW)
│
├── runtime (group) - Runtime state management
│   ├── show [task]              # Display runtime state (last_run, last_status)
│   └── reset [task]             # Reset runtime state for task or all tasks
│
├── export (group) - Export scheduling configs (PHASE 2)
│   ├── systemd <group>          # Generate systemd timer (replaces export-systemd)
│   └── cron <group>             # Generate crontab entry (replaces export-cron)
│
├── init [--force]               # Initialize config (existing)
├── status                       # Dashboard overview (NEW)
└── version                      # Show version info (check if exists)
```

### Command Explanations:

**task list vs task info:**
- `task list`: Shows table of ALL tasks with basic info (name, description, last status)
  ```
  NAME                DESCRIPTION                        LAST RUN            STATUS
  ─────────────────────────────────────────────────────────────────────────────────
  backup_database     Backup PostgreSQL to S3            2026-02-09 08:15    success
  check_disk_space    Monitor disk usage                 2026-02-09 08:10    failed
  lint_code           Run code linter                    never               -
  ```

- `task info <name>`: Shows FULL details for ONE task (command, working dir, env vars, config)
  ```
  Task: backup_database
  Description: Backup PostgreSQL database to S3
  Command: /usr/local/bin/backup.sh --destination s3://backups/
  
  Configuration:
    Working Directory: /opt/app
    Timeout: 300s
    Environment Variables:
      DB_HOST: localhost
      DB_NAME: production
  
  Runtime Status:
    Last Run: 2026-02-09 08:15:32
    Last Status: success
  
  Log Directory: ~/.config/signalbox/logs/backup_database/
  ```

**runtime show:**
Displays the runtime state files (`runtime/tasks/*.yaml`) which track execution history:
```
signalbox runtime show backup_database

Runtime State: backup_database
  Last Run: 2026-02-09 08:15:32
  Last Status: success
  Run Count: 1,234 (tracked in runtime state file)
  
Runtime File: ~/.config/signalbox/runtime/tasks/runtime_backup.yaml
```

**status (Dashboard):**
Quick overview of system health - recent activity, failures, currently running tasks:
```
signalbox status

Recent Activity (last 24h):
  Total Runs: 156
  Successes: 149 (95.5%)
  Failures: 7 (4.5%)

Recent Failures (last 5):
  ✗ check_disk_space    2026-02-09 08:15:30
  ✗ backup_remote       2026-02-09 06:00:12

Groups:
  daily_maintenance     Last run: 2h ago     Status: success
  monitoring           Last run: 5m ago     Status: success
```

**export (Deferred to Phase 2):**
This feature is larger than it appears and should be a separate discussion. It involves:
- Detecting system init system (systemd vs cron)
- Generating proper unit files with correct paths
- Installing timers with appropriate permissions
- Handling user vs system installations
- Cross-platform considerations

Recommend: Leave existing `export-systemd` and `export-cron` as-is for v1, improve in v2.

### Implementation Notes:

**No Backward Compatibility Needed:**
Since no official release exists, we can do a clean break. Old commands will simply stop working.

**Root-Level Shortcuts:**
Keep some shortcuts at root level for convenience:
```python
# Keep these for ease of use
signalbox run <name>       # Shortcut to task run <name>
signalbox validate         # Shortcut to config validate
signalbox list            # Shortcut to task list
```

**Click Group Implementation:**
```python
@click.group()
def cli():
    """Signalbox - Task automation and monitoring."""
    pass

@cli.group()
def task():
    """Task management commands."""
    pass

@task.command(name="run")
@click.argument("name", required=False)
@click.option("--all", "run_all", is_flag=True, help="Run all tasks")
def task_run(name, run_all):
    """Run a task or all tasks."""
    if run_all:
        # Run all tasks logic
        pass
    elif name:
        # Run single task logic
        pass
    else:
        click.echo("Error: Provide task name or use --all", err=True)
        sys.exit(2)

# Add root-level shortcut
@cli.command(name="run")
@click.argument("name")
def run_shortcut(name):
    """Run a task (shortcut to 'task run')."""
    # Call task_run implementation
    pass
```

**Files to Update:**
- `core/cli_commands.py` - restructure all commands into groups
- Update help text for all commands
- Ensure all commands work with new structure

---

## Priority 5: Log Management Suite (NEW COMMANDS)


### 5.1 New Command: `signalbox log list`

**Purpose:** Unified view of ALL task execution logs - showing every single run, not just the last run per task.

**Key Feature:** Each execution shows up as a separate row, so you can see the full history.

### Usage:
```bash
signalbox log list [OPTIONS]
```

### Options:
```
--task NAME              Filter to specific task
--status STATUS          Filter by status: success, failed, running
--failed                 Shortcut for --status failed
--success                Shortcut for --status success
--since DATE             Show logs since date (YYYY-MM-DD or "2 days ago")
--until DATE             Show logs until date
--today                  Show only today's logs
--last N                 Show last N runs (default: 50)
--limit N                Alias for --last
--format FORMAT          Output format: table (default), json, csv
--sort FIELD             Sort by: time (default), task, status, duration
--reverse                Reverse sort order
```

### Output Format (Table):

**Important:** Each run is a separate row, tasks can appear multiple times:

```
TASK NAME          STATUS    START TIME           DURATION    LOG FILE
─────────────────────────────────────────────────────────────────────────────────────
backup_database    success   2026-02-09 08:15:32  2.3s        logs/backup_database/20260209_081532.log
backup_database    success   2026-02-08 08:15:30  2.1s        logs/backup_database/20260208_081530.log
check_disk_space   failed    2026-02-09 08:15:30  0.1s        logs/check_disk_space/20260209_081530.log
check_disk_space   success   2026-02-09 06:00:00  0.1s        logs/check_disk_space/20260209_060000.log
system_update      success   2026-02-09 06:00:01  45.7s       logs/system_update/20260209_060001.log
lint_code          running   2026-02-09 08:16:00  -           logs/lint_code/20260209_081600.log
```

### Example Queries:
```bash
# See all runs from last 24 hours
signalbox log list --today

# See all failures
signalbox log list --failed

# See all runs of a specific task
signalbox log list --task backup_database

# See last 10 runs of any task
signalbox log list --last 10

# See runs from last week that failed
signalbox log list --failed --since "7 days ago"

# Export to CSV for analysis
signalbox log list --format csv > task_history.csv
```

### JSON Output Format:
```json
{
  "logs": [
    {
      "task": "backup_database",
      "status": "success",
      "start_time": "2026-02-09T08:15:32",
      "duration": 2.3,
      "log_file": "logs/backup_database/20260209_081532.log",
      "exit_code": 0
    },
    {
      "task": "backup_database",
      "status": "success",
      "start_time": "2026-02-08T08:15:30",
      "duration": 2.1,
      "log_file": "logs/backup_database/20260208_081530.log",
      "exit_code": 0
    }
  ],
  "total": 156,
  "filtered": 2,
  "filters_applied": {
    "task": "backup_database",
    "status": "all",
    "since": null
  }
}
```

### CSV Output Format:
```csv
task,status,start_time,duration,log_file,exit_code
backup_database,success,2026-02-09 08:15:32,2.3,logs/backup_database/20260209_081532.log,0
backup_database,success,2026-02-08 08:15:30,2.1,logs/backup_database/20260208_081530.log,0
```

### Implementation:

**New Function:** `core/log_manager.py::get_all_task_logs()`

```python
def get_all_task_logs(
    task_name: Optional[str] = None,
    status_filter: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    limit: Optional[int] = None,
    sort_by: str = "time",
    reverse: bool = False
) -> List[Dict]:
    """
    Get all task execution logs with optional filtering.
    
    Each log file represents one execution, so a task that ran
    100 times will have 100 entries in the results.
    
    Returns list of dicts with keys:
    - task: task name (str)
    - status: success/failed/running/unknown (str)
    - start_time: execution start (datetime)
    - duration: seconds (float) or None if running
    - log_file: absolute path (str)
    - exit_code: int or None
    
    Algorithm:
    1. Scan logs/ directory for all task subdirectories
    2. For each subdirectory, find all *.log files
    3. Parse filename timestamp (YYYYMMDD_HHMMSS.log format)
    4. Determine status from markers or runtime state
    5. Calculate duration if completed
    6. Apply filters (task, status, date range)
    7. Sort by specified field
    8. Limit results if requested
    9. Return structured data
    """
    logs_dir = get_logs_dir()  # e.g., ~/.config/signalbox/logs/
    all_logs = []
    
    # Scan all task directories
    for task_dir in os.listdir(logs_dir):
        task_path = os.path.join(logs_dir, task_dir)
        if not os.path.isdir(task_path):
            continue
        
        # Filter by task name if specified
        if task_name and task_dir != task_name:
            continue
        
        # Find all log files for this task
        for log_file in os.listdir(task_path):
            if not log_file.endswith('.log'):
                continue
            
            log_path = os.path.join(task_path, log_file)
            
            # Parse filename: YYYYMMDD_HHMMSS.log
            try:
                timestamp_str = log_file.replace('.log', '')
                start_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except ValueError:
                continue  # Skip malformed filenames
            
            # Filter by date range
            if since and start_time < since:
                continue
            if until and start_time > until:
                continue
            
            # Determine status
            status = detect_log_status(log_path)
            
            # Filter by status
            if status_filter and status != status_filter:
                continue
            
            # Calculate duration
            duration = calculate_log_duration(log_path, status)
            
            # Get exit code if available
            exit_code = get_exit_code(log_path)
            
            all_logs.append({
                "task": task_dir,
                "status": status,
                "start_time": start_time,
                "duration": duration,
                "log_file": log_path,
                "exit_code": exit_code
            })
    
    # Sort
    sort_key = {
        "time": lambda x: x["start_time"],
        "task": lambda x: x["task"],
        "status": lambda x: x["status"],
        "duration": lambda x: x["duration"] or 0
    }.get(sort_by, lambda x: x["start_time"])
    
    all_logs.sort(key=sort_key, reverse=reverse)
    
    # Limit
    if limit:
        all_logs = all_logs[:limit]
    
    return all_logs
```

**Status Detection Logic:**
```python
def detect_log_status(log_path: str) -> str:
    """Determine log status from markers and file properties."""
    # 1. Check for explicit markers
    if os.path.exists(f"{log_path}.success"):
        return "success"
    if os.path.exists(f"{log_path}.failed"):
        return "failed"
    
    # 2. Check runtime state
    task_name = os.path.basename(os.path.dirname(log_path))
    runtime_state = load_runtime_state().get("tasks", {}).get(task_name, {})
    log_timestamp = os.path.basename(log_path).replace('.log', '')
    if runtime_state.get("last_run") == log_timestamp:
        return runtime_state.get("last_status", "unknown")
    
    # 3. Check if recently modified (possibly still running)
    mtime = os.path.getmtime(log_path)
    if time.time() - mtime < 60:  # Modified in last minute
        return "running"
    
    # 4. Default
    return "unknown"
```

**Date Parsing:**
Support both absolute and relative dates:
```python
def parse_date_string(date_str: str) -> datetime:
    """Parse date string (absolute or relative)."""
    # Relative dates
    if date_str == "today":
        return datetime.now().replace(hour=0, minute=0, second=0)
    if date_str == "yesterday":
        return datetime.now().replace(hour=0, minute=0, second=0) - timedelta(days=1)
    
    # "N days ago", "N weeks ago"
    match = re.match(r"(\d+)\s+(day|week)s?\s+ago", date_str)
    if match:
        count, unit = int(match.group(1)), match.group(2)
        delta = timedelta(days=count) if unit == "day" else timedelta(weeks=count)
        return datetime.now() - delta
    
    # Absolute dates
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M")
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}")
```

**Files to Update:**
- `core/log_manager.py` - add `get_all_task_logs()` function
- `core/cli_commands.py` - add `log list` command in log group
- Add helper functions for status detection, duration calculation, date parsing

---

### 5.2 New Command: `signalbox log show`


**Purpose:** Display full log content for a specific task run.

### Usage:
```bash
# Show latest log for task
signalbox log show backup_database

# Show specific run by timestamp/ID
signalbox log show backup_database 20260209_081532

# Show Nth most recent
signalbox log show backup_database --last 2
```

### Options:
```
--last N       Show Nth most recent log (default: 1, meaning latest)
--pager        Force use of less/more for pagination
--no-pager     Print directly to stdout (no paging)
--raw          Show raw log without header/formatting
```

### Output Format:
```
═══════════════════════════════════════════════════════════════
Log: backup_database
Run: 2026-02-09 08:15:32
Status: success (exit code 0)
Duration: 2.3s
Log File: ~/.config/signalbox/logs/backup_database/20260209_081532.log
═══════════════════════════════════════════════════════════════

[Log content starts here]
Starting backup process...
Connecting to database: production
Creating dump file...
Uploading to S3: s3://backups/prod_20260209.sql.gz
Backup completed successfully
[Log content ends here]
```

### Implementation:
```python
@log_group.command(name="show")
@click.argument("task")
@click.argument("run_id", required=False)
@click.option("--last", default=1, help="Show Nth most recent run (1=latest)")
@click.option("--pager/--no-pager", default=None, help="Control paging behavior")
@click.option("--raw", is_flag=True, help="Show raw log without formatting")
def log_show(task, run_id, last, pager, raw):
    """Display full log content for a task run."""
    # Find log file
    if run_id:
        # Specific run by timestamp
        log_file = find_log_by_timestamp(task, run_id)
    else:
        # Nth most recent
        log_file = find_nth_recent_log(task, last)
    
    if not log_file or not os.path.exists(log_file):
        click.echo(f"Error: Log not found for task '{task}'", err=True)
        sys.exit(2)
    
    # Read log content
    with open(log_file, 'r') as f:
        content = f.read()
    
    if raw:
        # Just print log content
        click.echo(content)
    else:
        # Print with header
        status = detect_log_status(log_file)
        duration = calculate_log_duration(log_file, status)
        timestamp = extract_timestamp_from_filename(log_file)
        
        click.echo("═" * 70)
        click.echo(f"Log: {task}")
        click.echo(f"Run: {timestamp}")
        click.echo(f"Status: {status}")
        if duration:
            click.echo(f"Duration: {duration}s")
        click.echo(f"Log File: {log_file}")
        click.echo("═" * 70)
        click.echo()
        click.echo(content)
    
```

---

### 5.3 New Command: `signalbox log tail`

**Purpose:** Follow task logs in real-time (like `tail -f`).

### Usage:
```bash
# Follow latest log for task
signalbox log tail backup_database

# Show last 50 lines then follow
signalbox log tail backup_database --lines 50

# Just show last N lines (don't follow)
signalbox log tail backup_database --lines 20 --no-follow
```

### Options:
```
-f, --follow       Follow log updates in real-time (default: true)
-n, --lines N      Show last N lines initially (default: 10)
--no-follow        Just show last N lines and exit
```

### Implementation:
```python
@log_group.command(name="tail")
@click.argument("task")
@click.option("-f", "--follow/--no-follow", default=True, help="Follow log updates")
@click.option("-n", "--lines", default=10, help="Number of initial lines to show")
def log_tail(task, follow, lines):
    """Follow task logs in real-time."""
    # Find latest log file
    log_file = find_nth_recent_log(task, 1)
    
    if not log_file or not os.path.exists(log_file):
        click.echo(f"Error: No log found for task '{task}'", err=True)
        sys.exit(2)
    
    if follow:
        # Use tail -f subprocess for cross-platform support
        try:
            subprocess.run(["tail", f"-n{lines}", "-f", log_file])
        except KeyboardInterrupt:
            click.echo("\nStopped following log")
    else:
        # Just show last N lines
        try:
            result = subprocess.run(
                ["tail", f"-n{lines}", log_file],
                capture_output=True,
                text=True
            )
            click.echo(result.stdout)
        except Exception as e:
            # Fallback to Python implementation
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                for line in all_lines[-lines:]:
                    click.echo(line, nl=False)
```

---

### 5.4 Optional:  `signalbox log clear` Enhancement

**Current:** `clear-logs` command exists but could be improved.

**Enhancements:**
```bash
# Clear all logs
signalbox log clear

# Clear logs for specific task
signalbox log clear --task backup_database

# Clear old logs (keep recent)
signalbox log clear --older-than 30  # days

# Clear only failed logs
signalbox log clear --failed-only
```

This can be implemented later if the current `clear-logs` works fine.

---

### 5.5 Helper Function: `clear_task_logs()`

**Note:** The test calls this function, but we should determine if it's needed by the app or CLI.

**Decision:** Add it if we implement `signalbox log clear --task <name>`, otherwise skip.

```python
def clear_task_logs(task_name: str) -> bool:
    """Clear all logs for a specific task."""
    log_dir = get_task_log_dir(task_name)
    if not os.path.exists(log_dir):
        return False
    try:
        shutil.rmtree(log_dir)
        os.makedirs(log_dir, exist_ok=True)
        return True
    except Exception as e:
        click.echo(f"Error clearing logs for {task_name}: {e}", err=True)
        return False
```

---

## Priority 6: Additional Small Commands

### 6.1 `config path`

Simple command to print config directory:

```python
@config_group.command(name="path")
def config_path():
    """Print the configuration directory path."""
    mgr = ConfigManager()
    path = mgr.find_config_home()
    click.echo(path)
```

### 6.2 `config show`

Display current configuration or specific key:

```python
@config_group.command(name="show")
@click.argument("key", required=False)
def config_show(key):
    """Display configuration (all or specific key)."""
    mgr = ConfigManager()
    config = mgr.load_config()
    
    if key:
        # Show specific key (supports dot notation: tasks.backup.command)
        value = get_nested_value(config, key)
        if value is None:
            click.echo(f"Key '{key}' not found", err=True)
            sys.exit(2)
        click.echo(yaml.dump({key: value}))
    else:
        # Show all config
        click.echo(yaml.dump(config))
```

### 6.3 `version` Command

Check if this already exists. If not, add:

```python
@cli.command()
def version():
    """Show version information."""
    # Check if __version__ exists in core/__init__.py
    try:
        from core import __version__
        version_str = __version__
    except ImportError:
        version_str = "unknown"
    
    click.echo(f"Signalbox version {version_str}")
    click.echo(f"Python {sys.version.split()[0]}")
    click.echo(f"Config: {ConfigManager().find_config_home()}")
```

---

## Implementation Plan

### Sprint 1: Foundation (Week 1)
**Goal:** Core infrastructure changes

1. **Terminology Migration** (Priority 1)
   - Rename all internal functions (runtime, log_manager, executor)
   - Update all user-facing strings in CLI commands
   - Update config template and documentation
   - Test: Fresh `signalbox init` should use "tasks" everywhere

2. **XDG Support** (Priority 2)
   - Update `ConfigManager.find_config_home()`
   - Test manually with different env vars
   - Document in README

3. **Exit Codes** (Priority 3)
   - Fix `run_all()` to track failures and exit 1
   - Fix `validate()` to collect all errors  
   - Update `handle_exceptions()`
   - Add exit code table to README

**Deliverable:** Core app works with consistent terminology and proper exit codes.

---

### Sprint 2: Command Restructuring (Week 2)
**Goal:** New command structure with Click groups

1. **Create Click Groups**
   - Define groups: task, group, log, config, runtime
   - Move existing commands into appropriate groups
   - Add root-level shortcuts (run, list, validate)

2. **Update Command Names**
   - `run-group` → `group run`
   - `run-all` → `task run --all`
   - `list-groups` → `group list`
   - `clear-logs` → `log clear`

3. **Test All Commands**
   - Verify all commands work with new structure
   - Check help text is clear
   - Ensure shortcuts work

**Deliverable:** Restructured CLI with better organization.

---

### Sprint 3: Log Management Suite (Week 3)
**Goal:** Implement all log commands

1. **log list Command**
   - Implement `get_all_task_logs()` in `log_manager.py`
   - Add status detection logic
   - Add date parsing (absolute and relative)
   - Support filtering: --task, --status, --since, --until
   - Support formats: table, json, csv
   - Test with real log files

2. **log show Command**
   - Implement log file discovery
   - Add formatted output with header
   - Support --last, --raw, --pager options
   - Test edge cases (missing logs, malformed files)

3. **log tail Command**
   - Implement using subprocess tail -f
   - Add fallback for non-Unix systems
   - Handle Ctrl+C gracefully

**Deliverable:** Full log management capabilities.

---

### Sprint 4: Polish & Documentation (Week 4)
**Goal:** Small commands and documentation

1. **Small Commands**
   - Implement `config path`
   - Implement `config show`
   - Verify/add `version` command
   - Add root-level shortcuts

2. **Documentation**
   - Update README with all commands
   - Add exit code reference
   - Update all existing guides for "tasks" terminology
   - Add examples for log commands

3. **Testing & Validation**
   - Manual testing of all commands
   - Test error cases
   - Test with fresh config
   - Cross-platform check (macOS/Linux)

**Deliverable:** v1.0 ready for release.

---

## Future Enhancements (Post-V1)

These are good ideas to revisit after v1 stabilizes:

### Phase 2: Advanced Features

**status Dashboard Command:**
Quick overview of system health - shows recent activity, failures, running tasks, group status.
Requires: Runtime state tracking, log aggregation, possibly watch mode.

**task info Enhancements:**
Currently shows basic task config. Could add:
- Run statistics (count, success rate, avg duration)
- Recent history (last 5-10 runs)
- Groups this task belongs to

**Stats and Analytics:**
Track metrics like:
- Total runs per task
- Success/failure rates
- Average duration
- Trends over time

Implementation requires: Persistent stats storage (separate from logs), aggregation logic, decision on how stats interact with log clearing.

**export Improvements:**
Current export-systemd/export-cron are basic. Could enhance:
- Auto-detect init system
- Better permission handling (user vs system)
- Validation of generated files
- Direct installation option
- Cross-platform support

-**Global Flags:**
Add `--quiet`, `--verbose`, `--debug` flags at CLI root level to control output verbosity across all commands.

**--dry-run Support:**
Add dry-run mode to `task run` and `task run --all` to show what would execute without running.

**doctor Diagnostics:**
System health check command that validates:
- Config file syntax
- Task commands are executable
- Directory permissions
- Disk space
- Dead/orphaned log files

**runtime Management:**
Expand runtime commands to:
- Show detailed run history
- Reset runtime state selectively
- Export runtime data

---

## Open Questions

### Question 1: Date Parsing Library
**Options:**
- A) Use `dateutil` library (adds dependency, robust parsing)
- B) Implement simple parser for common cases (no dependency)

**Recommendation:** Start with B (simple parser), add A if users need more complex date formats.

---

### Question 2: Log Status Markers
**Current:** Uses `.success` and `.failed` marker files alongside logs.

**Options:**
- A) Continue with marker files (simple, reliable)
- B) Rely on runtime state only (cleaner file system)
- C) Hybrid: Use both with sync logic

**Recommendation:** Stick with A (current system) for v1, revisit in v2.

---

### Question 3: Output Formatting
**Options:**
- A) Add rich/colored output (requires `rich` or `colorama` dependency)
- B) Keep plain text (no dependencies)

**Recommendation:** B for v1 (keep it simple), A for v2 (better UX).

---

### Question 4: Stats Tracking
**Question:** How should task statistics work with log clearing?

**Options:**
- A) Stats derived from log files (cleared with logs)
- B) Stats in separate persistent storage (survive log clearing)
- C) Stats in runtime state (updated on each run)

**Recommendation:** Defer full stats to v2. For v1, show basic info from runtime state (last run, last status).

---

## Success Criteria

### V1 Release Ready When:

**Functionality:**
- [ ] All user-facing strings use "tasks" (not "scripts")
- [ ] XDG_CONFIG_HOME properly supported
- [ ] Exit codes follow POSIX conventions (0, 1, 2, 126, 130)
- [ ] `run all` continues through failures, exits 1 if any failed
- [ ] Commands organized into Click groups (task, group, log config, etc.)
- [ ] `signalbox log list` works with all filters (task, status, date, format)
- [ ] `signalbox log show <task>` displays full log content
- [ ] `signalbox log tail <task>` follows logs in real-time
- [ ] `signalbox config path` shows config directory
- [ ] `signalbox version` shows version info (if didn't exist)
- [ ] Root-level shortcuts work (run, list, validate)

**Documentation:**
- [ ] README updated with new command structure
- [ ] Exit code reference documented
- [ ] Log command examples added
- [ ] XDG config behavior documented
- [ ] All guides updated for "tasks" terminology

**Quality:**
- [ ] Manual testing on macOS/Linux
- [ ] Error messages are helpful
- [ ] Help text is clear and accurate
- [ ] Fresh `init` works correctly
- [ ] No regressions in existing functionality

**NOT REQUIRED for v1:**
- Test suite fixes (deferred)
- Full task stats/analytics
- `doctor` diagnostics command
- Color/rich output
- `--dry-run` flags
- Global `--quiet/--verbose` flags

---

*This specification is ready for implementation. Proceed sprint by sprint, validating each phase before moving to the next.*
