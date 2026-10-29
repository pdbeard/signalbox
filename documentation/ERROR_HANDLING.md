# Error Handling in Signalbox

## Overview

All parts of signalbox use the same method to handle errors. This method gives these results:
- **Predictable behavior**: all errors go to the command-line layer in the same way.
- **Correct exit codes**: shell scripts can find and handle failures.
- **Clear messages**: users can see what went wrong.
- **Separate jobs**: the code that runs tasks does not show messages.

## Exception Hierarchy

All signalbox exceptions come from `SignalboxError`:

```python
SignalboxError (base, exit code 1)
├── ConfigurationError (exit code 2)
├── TaskNotFoundError (exit code 3)
├── GroupNotFoundError (exit code 3)
├── ExecutionError (exit code 4)
│   └── ExecutionTimeoutError (exit code 4)
└── ValidationError (exit code 2)
```

## Exit Codes

| Code | Exception | Meaning |
|------|-----------|---------|
| 0 | Success | The command was successful |
| 1 | SignalboxError, or a task failed | A general error, or one or more tasks failed |
| 2 | ConfigurationError, ValidationError | The configuration is not correct, signalbox cannot load it, or the arguments are not correct |
| 3 | TaskNotFoundError, GroupNotFoundError | The task or the group does not exist |
| 4 | ExecutionError, ExecutionTimeoutError | Signalbox could not run the task, or the task did not stop before its time limit |
| 126 | PermissionError | The user does not have the necessary permission |
| 130 | KeyboardInterrupt | The user pushed Ctrl+C |

## Architecture

### Layer Separation

1. **Core modules** (for example, `executor.py` and `config.py`)
   - Raise an exception for each error.
   - Do not write error messages to the console.
   - Do the work: load the configuration, run tasks, write logs.

2. **Command-line layer** (`signalbox/commands/`)
   - Catch exceptions with the `@handle_exceptions` decorator (`signalbox/commands/utils.py`).
   - Show the error message to the user.
   - Exit with the correct code.

### Example Flow

```python
# In signalbox/executor.py
def _find_task(name, config):
    task = next((t for t in config["tasks"] if isinstance(t, dict) and t.get("name") == name), None)
    if not task:
        raise TaskNotFoundError(name)
    return task

# In signalbox/commands/task.py
@task.command(name="run")
@click.argument("name", required=False)
@handle_exceptions  # Catches and formats exceptions
def task_run(name, ...):
    config = load_config(suppress_warnings=True)
    run_task(name, config)  # Can raise TaskNotFoundError
```

When a user runs `signalbox run nonexistent`:
1. `_find_task()` raises `TaskNotFoundError("nonexistent")`.
2. `@handle_exceptions` catches the exception.
3. Signalbox writes `Error: Task 'nonexistent' not found` to stderr.
4. Signalbox exits with code 3.

## Usage in Scripts

### Shell Scripts
```bash
#!/bin/bash

# Run a task and check for errors
if signalbox run my_task; then
    echo "Success!"
else
    code=$?
    case $code in
        1) echo "Task failed" ;;
        3) echo "Task not found" ;;
        4) echo "Execution failed or timed out" ;;
        *) echo "Other error" ;;
    esac
    exit $code
fi
```

### Python Scripts
```python
import subprocess
import sys

result = subprocess.run(['signalbox', 'run', 'my_task'])

if result.returncode == 0:
    print("Success!")
elif result.returncode == 3:
    print("Task not found")
    sys.exit(1)
elif result.returncode in (1, 4):
    print("Task failed")
    sys.exit(1)
```

## Implementation Details

### Custom Exceptions

The exceptions are in `signalbox/exceptions.py`:

```python
class SignalboxError(Exception):
    """Base exception with message and exit_code attributes."""
    def __init__(self, message, exit_code=1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(self.message)
```

### Exception Handler Decorator

The decorator is in `signalbox/commands/utils.py`. This is a short version:

```python
def handle_exceptions(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            sys.exit(130)
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(2)
        except PermissionError as e:
            click.echo(f"Permission Denied: {e}", err=True)
            sys.exit(126)
        except SignalboxError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(e.exit_code)
        except Exception as e:
            click.echo(f"Unexpected error: {str(e)}", err=True)
            sys.exit(1)
    return wrapper
```

### Applying to Commands

Add the decorator to the command:

```python
@cli.command()
@click.argument('name')
@handle_exceptions  # Add this
def my_command(name):
    # Command logic that may raise exceptions
    pass
```

## Testing Error Handling

### Verify Exit Codes
```bash
# Should exit with code 3
signalbox run nonexistent_task
echo $?  # Should print 3

# Should exit with code 3
signalbox group run nonexistent_group
echo $?  # Should print 3

# Should exit with code 0
signalbox run hello
echo $?  # Should print 0
```

### Verify Error Messages
```bash
# Should print to stderr
signalbox run nonexistent 2>&1 | grep "Error:"
# Output: Error: Task 'nonexistent' not found
```

## Possible Future Changes

1. **Structured logging**: log levels (DEBUG, INFO, ERROR)
2. **More context**: the file, the line number, and a stack trace in debug mode
3. **Retries**: run a task again after a temporary failure
4. **Error hooks**: custom error handlers in the configuration
5. **Translations**: error messages in more than one language

## Related Documentation

- [Configuration Guide](CONFIG_GUIDE.md)
- [Writing Scripts](WRITING_SCRIPTS.md)
- [Execution Modes](EXECUTION_MODES.md)
