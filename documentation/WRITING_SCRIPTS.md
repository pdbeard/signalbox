# Writing Scripts for signalbox

This guide covers best practices for writing scripts that work well with signalbox.

## Exit Code Requirements

**All scripts must return proper exit codes:**
- **0** = Success ✅
- **Non-zero (1-255)** = Failure ❌

signalbox uses exit codes to determine if a script succeeded or failed. This is a universal standard across all programming languages and shells.

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

**Note:** In Go, returning from `main()` without calling `os.Exit()` defaults to exit code 0.

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

**Note:** `panic!()` in Rust will exit with a non-zero code automatically.

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

## Best Practices

### 1. Always Set Explicit Exit Codes

Don't rely on implicit success - always explicitly exit with 0 on success.

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

signalbox captures both stdout and stderr. Write errors to stderr for clarity.

**Good:**
```python
print(f"Error: {error}", file=sys.stderr)
```

**Bad:**
```python
print(f"Error: {error}")  # Goes to stdout
```

### 3. Use Meaningful Exit Codes (Optional)

While signalbox only distinguishes 0 vs non-zero, you can use different codes for different errors:

```python
# Exit codes
SUCCESS = 0
ERR_CONFIG = 1
ERR_CONNECTION = 2
ERR_TIMEOUT = 3

sys.exit(ERR_CONNECTION)
```

This helps with debugging when reviewing logs.

### 4. Make Scripts Executable

```bash
chmod +x your_script.sh
```

Then reference them directly in config:
```yaml
- name: my_script
  command: /path/to/script.sh
```

### 5. Use Absolute Paths or PATH

**Option 1: Absolute paths**
```yaml
command: /usr/local/bin/backup.sh
```

**Option 2: Ensure script is in PATH**
```yaml
command: backup.sh  # Works if in PATH
```

**Option 3: Use interpreter explicitly**
```yaml
command: python3 /path/to/script.py
command: node /path/to/script.js
```

### 6. Handle Signals Gracefully

For long-running scripts, handle interruption:

```python
import signal
import sys

def signal_handler(sig, frame):
    print("Interrupted", file=sys.stderr)
    sys.exit(130)  # Standard exit code for SIGINT

signal.signal(signal.SIGINT, signal_handler)
```

### 7. Validate Inputs

Check for required arguments or environment variables at the start:

```bash
#!/bin/bash

if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL not set" >&2
    exit 1
fi

# Continue with script...
```

## Testing Your Scripts

Before adding to signalbox, test exit codes manually:

```bash
# Run your script
./your_script.sh

# Check exit code
echo $?
# Should be 0 for success, non-zero for failure
```

## Common Issues

### Issue: Script always succeeds even when it should fail

**Cause:** Last command in script succeeds, overriding earlier failures.

**Solution:** Use `set -e` in Bash or explicit error handling.

### Issue: Script timeout even though it completed

**Cause:** Script runs longer than `default_timeout` (default: 300 seconds).

**Solution:** Increase timeout in config or for specific script:
```yaml
# In config.yaml
execution:
  default_timeout: 600  # 10 minutes
```

### Issue: Can't see error output

**Cause:** Errors printed to stdout instead of stderr.

**Solution:** Always write errors to stderr:
```python
print("Error", file=sys.stderr)  # Python
```
```bash
echo "Error" >&2  # Bash
```

## Exit Code Reference

Common exit codes your scripts might return:

| Code | Meaning | Example |
|------|---------|---------|
| 0 | Success | Everything completed successfully |
| 1 | General error | Something went wrong (most common failure) |
| 2 | Usage error | Invalid arguments or options |
| 126 | Cannot execute | Permission denied or not executable |
| 127 | Not found | Command/script doesn't exist |
| 130 | Interrupted | User pressed Ctrl+C |
| 137 | Killed | Process killed (often by timeout) |
| 143 | Terminated | Graceful shutdown signal received |

signalbox displays simple "success" or "failed" status based on exit code 0 vs non-zero.

## Related Documentation

- [Configuration Guide](CONFIG_GUIDE.md)
- [File Structure](FILE_STRUCTURE.md)
- [Execution Modes](EXECUTION_MODES.md)
