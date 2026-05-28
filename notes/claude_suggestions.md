# Signalbox – Code Review Suggestions

Three areas covered: **Security**, **Architecture**, and **Usability**.

---

## Security

### 1. `alerts.py` Hardcodes Config Path — Bug With Real Impact
**Files:** `core/alerts.py:18`, `core/alerts.py:103`

`alerts.py` duplicates path resolution logic, but gets it wrong:

```python
# alerts.py:17-19  (get_alerts_dir)
if not os.path.isabs(log_dir):
    config_dir = os.path.expanduser("~/.config/signalbox")  # ALWAYS hardcoded
    log_dir = os.path.join(config_dir, log_dir)
```

The same pattern appears again in `load_alerts()` at line 103. Compare this to `log_manager.py`, which correctly uses the config resolution system:

```python
# log_manager.py:14-17 — correct approach
from .config import _default_config_manager
config_home = _default_config_manager.find_config_home()
if not os.path.isabs(log_dir):
    log_dir = os.path.join(config_home, log_dir)
```

**Impact:** Users who set `SIGNALBOX_HOME` or `XDG_CONFIG_HOME` will have tasks execute and write alert logs to their custom location, but `signalbox alerts list` will silently read from `~/.config/signalbox` instead — returning empty or stale results. Alerts will appear lost.

**Fix:** Replace both hardcoded fallbacks in `alerts.py` with the same `_default_config_manager.find_config_home()` call that `log_manager.py` uses.

---

### 2. Log File Permission Race Condition
**File:** `core/log_manager.py:68-82`

```python
with open(log_file, "w") as f:   # created with process umask (may be 022 = world-readable)
    f.write(...)

os.chmod(log_file, 0o600)         # secured only after write completes
```

If the task command captures passwords, tokens, or other sensitive output, that content is world-readable during the write. On a multi-user system, another process could read it in that window.

**Fix:** Create the file with restrictive permissions from the start using `os.open()`:

```python
fd = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(...)
# No chmod needed — file was never world-readable
```

---

### 3. macOS Notification — Incomplete Escaping
**File:** `core/notifications.py:44-48`

The macOS notification helper escapes double quotes but not backslashes:

```python
title = title.replace('"', '\\"')
message = message.replace('"', '\\"')
script = f'display notification "{message}" with title "{title}"'
```

A message containing a literal backslash (e.g., from a Windows path in output, or `\n` in a log line) could produce malformed AppleScript. This is low severity since the input comes from internally-generated alert messages, but it is incomplete escaping.

**Fix:** Escape backslashes before escaping quotes:
```python
title = title.replace("\\", "\\\\").replace('"', '\\"')
message = message.replace("\\", "\\\\").replace('"', '\\"')
```

---

### 4. `clear_all_logs()` Uses Unresolved Relative Path
**File:** `core/log_manager.py:276-285`

```python
def clear_all_logs():
    log_dir = get_config_value("paths.log_dir", "logs")

    if not os.path.exists(log_dir):  # checked relative to CWD, not config home
        return False

    for root, dirs, files in os.walk(log_dir):
        ...
```

Unlike every other log function in the same file, `clear_all_logs()` does not resolve a relative `log_dir` against `config_home`. If called from a directory that happens to have a `logs/` subfolder (e.g., the project repo), it could delete unrelated files.

**Fix:** Apply the same resolution pattern used in `get_task_log_dir()`:
```python
from .config import _default_config_manager
config_home = _default_config_manager.find_config_home()
if not os.path.isabs(log_dir):
    log_dir = os.path.join(config_home, log_dir)
```

---

### 5. `shell=True` — Documented but Worth Hardening
**File:** `core/executor.py:72`

```python
result = subprocess.run(task["command"], shell=True, ...)
```

The intent is intentional and documented. The risk is that if any process can write to task YAML files, they can execute arbitrary commands under the user's identity at the next scheduled run. Signalbox's SECURITY.md acknowledges this, but no technical controls enforce it.

**Suggestions:**
- Add a `signalbox config check-permissions` command that warns if the config directory (or any task file) is writable by anyone other than the owner.
- Log the full command being executed at the start of each log file (already done), but also emit a DEBUG-level audit entry to a separate append-only audit log so that what was executed is always traceable even if the normal log rotates.

---

## Architecture

### 6. `run_task()` Ignores Its Own Parameter, Then Reloads Config
**File:** `core/executor.py:23-47`

`run_task(name, config)` receives the loaded config as a parameter, then immediately throws it away:

```python
def run_task(name, config):
    from . import validator, config as config_mod

    validation_result = validator.validate_configuration()   # re-validates from disk
    config = config_mod.load_config(suppress_warnings=True)  # re-loads from disk
```

This means every single task run — including tasks inside a group — independently re-reads and re-validates the YAML files from disk. For a group of 10 parallel tasks, config is parsed 10 times simultaneously. It also hides a subtle bug: changes to the in-memory config between the original load and this reload could cause divergence.

**Suggestions:**
- Remove the config reload and use the `config` parameter as intended.
- Move the validation call out of `run_task()` to the CLI layer, where it runs once before any execution begins.

---

### 7. Inconsistent Error Handling Patterns
**Files:** `core/executor.py`, `core/exporters.py`, `core/helpers.py`

The project uses three different error-reporting patterns with no consistent convention:

| Pattern | Location | Example |
|---------|----------|---------|
| Raise custom exceptions | `executor.py` | `raise TaskNotFoundError(name)` |
| Return result objects | `exporters.py` | `return ExportResult(success=False, error=...)` |
| Print and continue | `helpers.py` | `click.echo(f"Warning: Failed to load {filepath}: {e}")` |

Callers can't know which pattern to expect from any given function, which makes error paths hard to reason about and test.

**Suggestion:** The exception-based approach in `executor.py` is the cleanest. `ExportResult` in `exporters.py` and the warn-and-continue pattern in `helpers.py` are worth migrating. At minimum, document the intended pattern in AGENTS.md.

---

### 8. Silent Backwards-Compat Fallback to a Defunct Config Key

**File:** `core/notifications.py:121-126`

The two-namespace design in `signalbox.yaml` is correct and intentional — `alerts.notifications.*` fires when task output matches an alert pattern, while `group_notifications.*` fires after a group finishes executing. These are distinct features.

The issue is narrower: `notify_execution_result()` falls back to a `notifications.*` key that no longer exists in the config schema:

```python
enabled = get_config_value("group_notifications.enabled",
                           get_config_value("notifications.enabled", True))
```

`notifications.enabled` is not in `signalbox.yaml`. The current schema uses `alerts.notifications.enabled` for alert-pattern notifications and `group_notifications.enabled` for group summary notifications. The fallback key appears to be the old schema name from before the feature was split into two namespaces.

**Impact:** Any user with an old config that has `notifications.enabled: false` will have that silently respected through the fallback — but they'll have no idea why, and no indication that they're using a deprecated key. New users have no way of knowing the old key ever existed.

**Suggestion:** Remove the fallback to `notifications.*` since it no longer exists in the shipped config. If old user configs must be supported through a transition period, emit a one-time deprecation warning when the old key is detected rather than silently translating it at every call site.

---

### 9. `alerts.py` Duplicates Path Resolution Logic That Already Exists
**File:** `core/alerts.py:12-21` and `98-104`

This is both an architecture issue and the root cause of bug #1 above. The same "resolve log_dir to absolute path" logic exists in `alerts.py` (incorrectly) and `log_manager.py` (correctly). When the correct version was added to `log_manager.py`, `alerts.py` was not updated.

**Suggestion:** Extract the path resolution into a shared helper function — perhaps `get_resolved_log_dir()` in `log_manager.py` or `helpers.py` — and have both modules call it. This also prevents the same bug from recurring if a third module needs the same logic.

---

### 10. The `run_task()` Function Has Too Many Responsibilities
**File:** `core/executor.py:23-137`

A single call to `run_task()` currently: validates config, reloads config, finds the task, creates a log directory, runs the subprocess, writes the log, checks alert patterns, saves each alert, sends notifications per alert, rotates old logs, saves runtime state, and updates in-memory state.

This makes the function hard to test (you need to mock ~6 external systems) and hard to modify (changing notification logic requires understanding execution logic).

**Suggestion:** The immediate win is separating the pre/post execution concerns:
```python
def run_task(name, config):
    task = _find_task(name, config)
    result = _execute(task)
    _post_execution(name, task, result, config)
    return result.returncode == 0
```

Even this simple split would make unit testing of execution vs. logging vs. notifications independently straightforward.

---

## Usability

### 11. Config Validation Runs on Every Task Execution
**File:** `core/executor.py:42-44`

```python
validation_result = validator.validate_configuration()
if validation_result.errors or validation_result.warnings:
    click.echo("Some configuration errors or warnings were found...")
```

Users running `signalbox run my-task` will see a validation warning before their task output every time, even for warnings that are irrelevant to the task being run. This trains users to ignore the warning banner.

**Suggestion:** Remove validation from the hot path. Validate once at startup/init, or only on the `signalbox validate` command. If a task truly cannot run because of a config error, that will surface as a `TaskNotFoundError` or subprocess failure naturally.

---

### 12. "Not Found" Errors Give No Guidance
**Files:** `core/exceptions.py:31-33`, `core/exceptions.py:39-41`

```
Task 'backup_db' not found
```

Users who make a typo or forget a task name get no indication of what tasks do exist or whether they are close.

**Suggestion:** Pass available names into the exception so the error message can help:

```
Task 'backup_db' not found. Available tasks: backup-db, backup-files, backup-s3
```

The exceptions module's `TaskNotFoundError.__init__` only takes `task_name`, so the calling site in `executor.py:51` would need to build the message there and pass it through.

---

### 13. `signalbox run` Silently Validates and Reloads — Then Prints a Blank Line
**File:** `core/executor.py:70`

```python
click.echo("")  # Add a blank line before each task execution output
```

When running a group of tasks serially or in parallel, each task prints an empty line, then "Running task-name...", then output. Combined with the validation warning (issue #11), the first few lines users see when running a group are noise before any real output starts.

**Suggestion:** Remove the unconditional blank line from `run_task()`. The calling group runners in `run_group_serial()` and `run_group_parallel()` already print `"Running {task_name}..."` — the blank line adds visual padding that compounds when tasks are running in parallel and output is interleaved.

---

### 14. Installation Story Has an Unnecessary Friction Point
**Files:** `README.md`, `pyproject.toml`

Recommended install is `pipx install .` which requires the user to have already cloned the repo. This is fine for local tools, but there is no published PyPI package, meaning there is no `pipx install signalbox`. The README does not state this clearly — a new user might try `pipx install signalbox` and get either nothing or the wrong package.

Additionally, `signalbox init` must be run after install, but nothing in the tool itself tells the user this. If a user runs `signalbox list` before `signalbox init`, they get an error about missing config rather than "Run `signalbox init` first."

**Suggestions:**
- Add a friendly first-run detection: if config home has no `config/signalbox.yaml`, print: *"No configuration found. Run `signalbox init` to get started."*
- Clarify in the README that the tool is local-source-only, not on PyPI.

---

### 15. Log Format Uses Non-Standard Field Name
**File:** `core/log_manager.py:72-73`

```python
f.write(f"Return code: {return_code}\n")
```

Most Unix tooling, CI systems, and log parsers expect `exit code` or `exit status`. The current label `Return code` is technically accurate but inconsistent with the ecosystem and harder to grep for. It also means `parse_log_metadata()` at line 355 has to special-case `Return code:` when parsing, rather than using a standard pattern.

---

## Summary

| # | Area | Severity | Location |
|---|------|----------|----------|
| 1 | Security | High | `alerts.py:18, 103` — hardcoded config path causes alerts to read/write wrong directory |
| 2 | Security | Medium | `log_manager.py:68-82` — log file world-readable during write window |
| 3 | Security | Low | `notifications.py:44-48` — incomplete AppleScript escaping |
| 4 | Security | Medium | `log_manager.py:276` — `clear_all_logs` uses unresolved relative path |
| 5 | Security | Informational | `executor.py:72` — `shell=True` by design; consider audit log + permission check command |
| 6 | Architecture | High | `executor.py:40-47` — `run_task` ignores its `config` parameter and reloads from disk |
| 7 | Architecture | Medium | `executor.py`, `exporters.py` — inconsistent exception vs result-object error handling |
| 8 | Architecture | Low | `notifications.py:121-126` — silent fallback to defunct `notifications.*` key; schema split is correct but old key should be removed or warned on |
| 9 | Architecture | Medium | `alerts.py:12-21, 98-104` — duplicated path resolution, root cause of bug #1 |
| 10 | Architecture | Medium | `executor.py:23-137` — `run_task` does too much; hard to test in isolation |
| 11 | Usability | Medium | `executor.py:42-44` — validation runs on every task execution, creates noise |
| 12 | Usability | Medium | `exceptions.py:31, 39` — "not found" errors provide no available-names guidance |
| 13 | Usability | Low | `executor.py:70` — unconditional blank line adds noise in group output |
| 14 | Usability | Medium | `README.md` — no first-run guidance in the tool itself; PyPI status unclear |
| 15 | Usability | Low | `log_manager.py:73` — `Return code:` is non-standard vs ecosystem's `exit code` |
