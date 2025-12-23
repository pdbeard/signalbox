# Error Handling in Signalbox

## Overview

Signalbox implements a consistent error handling strategy across all components to ensure:
- **Predictable behavior**: All errors propagate consistently
- **Proper exit codes**: Shell scripts can detect and handle failures
- **Clear messages**: Users understand what went wrong
- **Separation of concerns**: Execution logic doesn't handle display

## Exception Hierarchy

All signalbox exceptions inherit from `SignalboxError`:

```python
SignalboxError (base, exit code 1)
├── ConfigurationError (exit code 2)
├── ScriptNotFoundError (exit code 3)
├── GroupNotFoundError (exit code 3)
├── ExecutionError (exit code 4)
│   └── ExecutionTimeoutError (exit code 4)
├── ValidationError (exit code 5)
├── ExportError (exit code 6)
└── LogError (exit code 7)
```

## Exit Codes

| Code | Exception | Meaning |
|------|-----------|---------|
| 0 | Success | Command completed successfully |
| 1 | SignalboxError | Generic error |
| 2 | ConfigurationError | Configuration invalid or cannot be loaded |
| 3 | ScriptNotFoundError/GroupNotFoundError | Requested item not found |
| 4 | ExecutionError/ExecutionTimeoutError | Script execution failed |
| 5 | ValidationError | Configuration validation failed |
| 6 | ExportError | Export operation failed |
| 7 | LogError | Log operation failed |

## Architecture

### Layer Separation

1. **Core Modules** (executor.py, etc.)
   - Raise exceptions for all errors
   - Don't print to console
   - Focus on business logic

2. **CLI Layer** (cli_commands.py)
   - Catch exceptions with `@handle_exceptions` decorator
   - Format error messages for users
   - Exit with appropriate codes

### Example Flow

```python
# In executor.py
def run_script(name, config):
    script = next((s for s in config['scripts'] if s['name'] == name), None)
    if not script:
        raise ScriptNotFoundError(name)  # Raises exception
    # ... execution logic

# In cli_commands.py
@cli.command()
@click.argument('name')
@handle_exceptions  # Catches and formats exceptions
def run(name):
    config = load_config()
    run_script(name, config)  # May raise ScriptNotFoundError
```

When user runs `signalbox run nonexistent`:
1. `run_script()` raises `ScriptNotFoundError("nonexistent")`
2. `@handle_exceptions` catches it
3. Prints: `Error: Script 'nonexistent' not found` to stderr
4. Exits with code 3

## Benefits Over Previous Approach

### Before (Inconsistent)
```python
# executor.py - returned False
def run_script(name, config):
    if not script:
        click.echo(f"Script {name} not found")
        return False

# cli_commands.py - no error code
def run(name):
    run_script(name, config)
    # No way to know if it failed
```

**Problems:**
- Mixed concerns (executor printing to console)
- No exit codes (shell scripts can't detect failure)
- Inconsistent error handling across commands

### After (Consistent)
```python
# executor.py - raises exception
def run_script(name, config):
    if not script:
        raise ScriptNotFoundError(name)

# cli_commands.py - handles display and exit
@handle_exceptions
def run(name):
    run_script(name, config)
```

**Benefits:**
- Clear separation: execution vs. display
- Proper exit codes for scripting
- Consistent error handling
- Better testability

## Usage in Scripts

### Shell Scripts
```bash
#!/bin/bash

# Run script and check for errors
if signalbox run my_script; then
    echo "Success!"
else
    code=$?
    case $code in
        3) echo "Script not found" ;;
        4) echo "Execution failed" ;;
        *) echo "Unknown error" ;;
    esac
    exit $code
fi
```

### Python Scripts
```python
import subprocess
import sys

result = subprocess.run(['signalbox', 'run', 'my_script'])

if result.returncode == 0:
    print("Success!")
elif result.returncode == 3:
    print("Script not found")
    sys.exit(1)
elif result.returncode == 4:
    print("Execution failed")
    sys.exit(1)
```

## Implementation Details

### Custom Exceptions

Located in `core/exceptions.py`:

```python
class SignalboxError(Exception):
    """Base exception with message and exit_code attributes."""
    def __init__(self, message, exit_code=1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(self.message)
```

### Exception Handler Decorator

Located in `core/cli_commands.py`:

```python
def handle_exceptions(func):
    """Decorator to handle exceptions consistently."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SignalboxError as e:
            click.echo(f"Error: {e.message}", err=True)
            sys.exit(e.exit_code)
        except Exception as e:
            click.echo(f"Unexpected error: {str(e)}", err=True)
            sys.exit(1)
    return wrapper
```

### Applying to Commands

Simply add the decorator:

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
signalbox run nonexistent_script
echo $?  # Should print 3

# Should exit with code 3
signalbox run-group nonexistent_group
echo $?  # Should print 3

# Should exit with code 0
signalbox run hello
echo $?  # Should print 0
```

### Verify Error Messages
```bash
# Should print to stderr
signalbox run nonexistent 2>&1 | grep "Error:"
# Output: Error: Script 'nonexistent' not found
```

## Future Enhancements

1. **Structured Logging**: Add proper logging with levels (DEBUG, INFO, ERROR)
2. **Error Context**: Include more context (file, line number, stack trace in debug mode)
3. **Error Recovery**: Implement retry logic for transient failures
4. **Error Hooks**: Allow custom error handlers via configuration
5. **Localization**: Support error messages in multiple languages

## Related Documentation

- [Configuration Guide](CONFIG_GUIDE.md)
- [Writing Scripts](WRITING_SCRIPTS.md)
- [Execution Modes](EXECUTION_MODES.md)
