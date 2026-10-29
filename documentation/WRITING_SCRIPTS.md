# Writing Scripts for signalbox

## ⚠️ Security First

**Signalbox runs commands in a shell, with all the permissions of your user.** A command can do these things:
- Read and write all files that you can access
- Make network connections
- Run all programs
- Delete data

**Read each script before you add it to your configuration.** For the security rules, refer to [SECURITY.md](../SECURITY.md).

---

This guide tells you how to write scripts that work well with signalbox. In this guide, a script is the program that the `command` of a task runs.

## Exit Code Requirements

**All scripts must return the correct exit code:**
- **0** = Success ✅
- **Not 0 (1-255)** = Failure ❌

Signalbox uses the exit code to find if a script was successful. All programming languages and shells use this rule.

## Language-Specific Examples

### Bash Scripts

**Recommended approach:**
```bash
#!/bin/bash
set -e  # Exit immediately if any command fails
set -u  # Exit if undefined variable is used
set -o pipefail  # Exit if any command in a pipeline fails

# Your script logic here
echo "Starting backup..."
backup_database
echo "Backup complete"

exit 0  # Explicit success
```

**With error handling:**
```bash
#!/bin/bash

if backup_database; then
    echo "Success"
    exit 0
else
    echo "Backup failed" >&2
    exit 1
fi
```

**Common pitfall:**
```bash
#!/bin/bash
# BAD - exit code is from last command only!
some_command_that_fails
echo "Done"  # Always succeeds, so script exits 0
```

### Python Scripts

**Recommended approach:**
```python
#!/usr/bin/env python3
import sys

def main():
    try:
        # Your script logic here
        print("Processing data...")
        result = process_data()
        print(f"Success: {result}")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
```

**Without exceptions:**
```python
#!/usr/bin/env python3
import sys

def main():
    result = do_something()
    
    if result:
        print("Success")
        sys.exit(0)
    else:
        print("Failed", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Go Programs

**Recommended approach:**
```go
package main

import (
    "fmt"
    "os"
)

func run() error {
    // Your program logic here
    fmt.Println("Processing...")
    
    if err := doSomething(); err != nil {
        return fmt.Errorf("operation failed: %w", err)
    }
    
    fmt.Println("Success")
    return nil
}

func main() {
    if err := run(); err != nil {
        fmt.Fprintf(os.Stderr, "Error: %v\n", err)
        os.Exit(1)
    }
    os.Exit(0)
}
```

**Note:** in Go, if `main()` returns without `os.Exit()`, the exit code is 0.

### Rust Programs

**Recommended approach:**
```rust
use std::process;

fn run() -> Result<(), Box<dyn std::error::Error>> {
    // Your program logic here
    println!("Processing...");
    
    do_something()?;
    
    println!("Success");
    Ok(())
}

fn main() {
    if let Err(e) = run() {
        eprintln!("Error: {}", e);
        process::exit(1);
    }
    process::exit(0);
}
```

**Note:** in Rust, `panic!()` exits with an exit code that is not 0.

### Node.js Scripts

**Recommended approach:**
```javascript
#!/usr/bin/env node

async function main() {
    try {
        console.log('Processing...');
        await doSomething();
        console.log('Success');
        process.exit(0);
    } catch (error) {
        console.error('Error:', error.message);
        process.exit(1);
    }
}

main();
```


## Adding Alerts to Tasks

You can add alerts to a task in its YAML file. An alert finds a pattern in the output and can send a notification.

### Example

```yaml
tasks:
    - name: check_website_health
        command: ./check_website.sh
        description: Check website status
        alerts:
            - pattern: "HTTP 5.."
                title: "Website Error"
                message: "[CRITICAL] Website returned 5xx error!"
                severity: critical
            - pattern: "timeout"
                title: "Connection Timeout"
                message: "[Warning] Website check timed out"
                severity: warning
            - pattern: "^OK"
                title: "Website Status"
                message: "Website is healthy"
                severity: info
                notify: true           # Override: send notification for info alert
                on_failure_only: false # Override: always notify
```

**Alert fields:**
- `pattern` (necessary): the regular expression or text to find in the output
- `message` (necessary): the text that signalbox records and shows in the notification
- `severity` (optional): `info`, `warning` or `critical`. The default is `info`.
- `title` (optional): the title of the notification. The default is `"Alert: {task_name}"`.
- `notify` (optional): replaces the global setting `alerts.notifications.enabled` for this alert
- `on_failure_only` (optional): replaces the global setting `alerts.notifications.on_failure_only` for this alert

Signalbox examines the alerts after the task stops. This is also true when the task stops at its time limit. If a pattern matches, signalbox does these steps:
1. It shows the alert in the console and records it in the alert history.
2. It sends a notification if the global settings and the settings of the alert let it.

### Per-Alert Notification Control

Each alert can have its own notification settings:

```yaml
alerts:
  # This info alert will send notifications (overriding global on_failure_only)
  - pattern: "Backup complete"
    message: "Daily backup successful"
    severity: info
    notify: true           # Force notification
    on_failure_only: false # Always notify, even for info
  
  # This critical alert won't send notifications
  - pattern: "ERROR"
    message: "Error detected"
    severity: critical
    notify: false  # Disable notification (still logged)
```

### Viewing Alerts

To see the recent alerts, use this command:
```bash
signalbox alerts
```
You can filter by task name, severity or age:
```bash
signalbox alerts check_website_health --severity critical --days 7
```

---
## Best Practices

### 1. Always Set Explicit Exit Codes

Do not let the script exit with the code of its last command by accident. Exit with 0 when the script is successful.

**Good:**
```bash
#!/bin/bash
set -e
# ... commands ...
exit 0
```

**Bad:**
```bash
#!/bin/bash
# ... commands ...
# (no explicit exit - may not be 0 if last command failed)
```

### 2. Write Errors to STDERR

Signalbox records stdout and stderr. Write errors to stderr. Thus, the errors are easy to find.

**Good:**
```python
print(f"Error: {error}", file=sys.stderr)
```

**Bad:**
```python
print(f"Error: {error}")  # Goes to stdout
```

### 3. Use Meaningful Exit Codes (Optional)

Signalbox only examines if the exit code is 0. But you can use different codes for different errors:

```python
# Exit codes
SUCCESS = 0
ERR_CONFIG = 1
ERR_CONNECTION = 2
ERR_TIMEOUT = 3

sys.exit(ERR_CONNECTION)
```

Different codes help you find the cause of a failure in the logs.

### 4. Make Scripts Executable

```bash
chmod +x your_script.sh
```

Then use them directly in the configuration:
```yaml
- name: my_script
  command: /path/to/script.sh
```

### 5. Use Absolute Paths or PATH

**Option 1: Absolute paths**
```yaml
command: /usr/local/bin/backup.sh
```

**Option 2: Make sure that the script is in PATH**
```yaml
command: backup.sh  # Works if in PATH
```

**Option 3: Give the interpreter in the command**
```yaml
command: python3 /path/to/script.py
command: node /path/to/script.js
```

### 6. Handle Signals Gracefully

If a script runs for a long time, handle interrupts:

```python
import signal
import sys

def signal_handler(sig, frame):
    print("Interrupted", file=sys.stderr)
    sys.exit(130)  # Standard exit code for SIGINT

signal.signal(signal.SIGINT, signal_handler)
```

### 7. Validate Inputs

At the start, make sure that the necessary arguments and environment variables are available:

```bash
#!/bin/bash

if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL not set" >&2
    exit 1
fi

# Continue with script...
```

## Testing Your Scripts

Before you add a script to signalbox, test its exit codes manually:

```bash
# Run your script
./your_script.sh

# Check exit code
echo $?
# Should be 0 for success, non-zero for failure
```

## Common Issues

### Problem: the script is always successful, also when it must fail

**Cause:** the last command of the script is successful. Its exit code replaces the earlier failures.

**Solution:** use `set -e` in Bash, or handle errors in the script.

### Problem: the task stops at its time limit before the script is complete

**Cause:** the script runs longer than `default_timeout` (300 seconds by default).

**Solution:** increase the time limit in `signalbox.yaml`, or set a time limit for the task:
```yaml
# In signalbox.yaml
execution:
  default_timeout: 600  # 10 minutes

# Or in the task
tasks:
  - name: long_backup
    command: ./backup.sh
    description: Nightly backup
    timeout: 1800  # 30 minutes
```

### Problem: you cannot see the error output

**Cause:** the script writes errors to stdout, not to stderr.

**Solution:** write errors to stderr:
```python
print("Error", file=sys.stderr)  # Python
```
```bash
echo "Error" >&2  # Bash
```

## Exit Code Reference

These are the usual exit codes that a script can return:

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Success | The script was successful |
| 1 | General error | Something went wrong (the most usual failure) |
| 2 | Usage error | Incorrect arguments or options |
| 126 | Cannot run | No permission, or the file is not executable |
| 127 | Not found | The command or the script does not exist |
| 130 | Interrupted | The user pushed Ctrl+C |
| 137 | Killed | Something stopped the process with SIGKILL |
| 143 | Terminated | The process received the signal to stop (SIGTERM) |

Signalbox shows "success" if the exit code is 0, and "failed" for all other codes. When a task stops at its time limit, signalbox records `Return code: -9` in the log.

## Related Documentation

- [Configuration Guide](CONFIG_GUIDE.md)
- [File Structure](FILE_STRUCTURE.md)
- [Execution Modes](EXECUTION_MODES.md)
