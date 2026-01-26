# Log management functionality for signalbox

import os
from datetime import datetime, timedelta
from .config import get_config_value
from .helpers import format_timestamp


def get_script_log_dir(script_name):
    """Get the log directory path for a script."""
    log_dir = get_config_value("paths.log_dir", "logs")
    return os.path.join(log_dir, script_name)


def ensure_log_dir(script_name):
    """Ensure the log directory exists for a script."""
    script_log_dir = get_script_log_dir(script_name)
    if not os.path.exists(script_log_dir):
        os.makedirs(script_log_dir)


def get_log_path(script_name, timestamp=None):
    """Get the full path for a log file.

    Args:
            script_name: Name of the script
            timestamp: Optional timestamp string, defaults to current time

    Returns:
            str: Full path to the log file
    """
    if timestamp is None:
        timestamp = format_timestamp(datetime.now())

    log_dir = get_config_value("paths.log_dir", "logs")
    return os.path.join(log_dir, script_name, f"{timestamp}.log")


def write_execution_log(log_file, command, return_code, stdout, stderr):
    """Write execution results to a log file.

    Args:
            log_file: Path to the log file
            command: The command that was executed
            return_code: Exit code from the command
            stdout: Standard output from the command
            stderr: Standard error from the command
    """
    # Security: Set restrictive permissions (owner read/write only)
    # This prevents other users from reading potentially sensitive log output
    import os

    # Check max log file size to prevent disk filling attacks
    max_log_size = get_config_value("logging.max_file_size_mb", 100) * 1024 * 1024
    content_size = len(command) + len(str(return_code)) + len(stdout) + len(stderr)

    if content_size > max_log_size:
        # Truncate output if too large
        truncation_msg = f"\n\n[OUTPUT TRUNCATED - exceeded {max_log_size / (1024*1024):.1f}MB limit]\n"
        remaining_size = max_log_size - len(command) - len(str(return_code)) - len(truncation_msg)
        half_size = remaining_size // 2
        stdout = stdout[:half_size] + truncation_msg + stdout[-half_size:] if len(stdout) > half_size else stdout
        stderr = stderr[:half_size] + truncation_msg + stderr[-half_size:] if len(stderr) > half_size else stderr

    with open(log_file, "w") as f:
        if get_config_value("logging.include_command", True):
            f.write(f"Command: {command}\n")

        if get_config_value("logging.include_return_code", True):
            f.write(f"Return code: {return_code}\n")

        if get_config_value("execution.capture_stdout", True):
            f.write("STDOUT:\n" + stdout + "\n")

        if get_config_value("execution.capture_stderr", True):
            f.write("STDERR:\n" + stderr + "\n")

    # Set secure permissions: 0o600 (owner read/write only)
    os.chmod(log_file, 0o600)


def rotate_logs(script):
    """Rotate logs for a script based on configured limits.

    Supports two rotation types:
    - 'count': Keep only the N most recent log files
    - 'age': Delete log files older than N days

    Args:
            script: Script configuration dict with optional 'log_limit' setting
    """
    import fcntl
    import tempfile

    name = script["name"]
    script_log_dir = get_script_log_dir(name)

    if not os.path.exists(script_log_dir):
        return

    # Security: Use file locking to prevent race conditions
    # Multiple concurrent executions could corrupt log rotation
    lock_file = os.path.join(tempfile.gettempdir(), f"signalbox_rotate_{name}.lock")

    try:
        with open(lock_file, "w") as lock:
            # Try to acquire exclusive lock (non-blocking)
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                # Another process is rotating logs, skip
                return

            # Get log limit settings
            default_limit = get_config_value("default_log_limit", {"type": "count", "value": 10})
            log_limit = script.get("log_limit", default_limit)

            log_files = os.listdir(script_log_dir)

            if log_limit["type"] == "count":
                _rotate_by_count(script_log_dir, log_files, log_limit["value"])
            elif log_limit["type"] == "age":
                _rotate_by_age(script_log_dir, log_files, log_limit["value"])

            # Lock is automatically released when file is closed
    except Exception as e:
        # Don't fail the entire script execution if rotation fails
        import click

        click.echo(f"Warning: Log rotation failed for {name}: {e}", err=True)


def _rotate_by_count(script_log_dir, log_files, max_count):
    """Keep only the most recent N log files.

    Args:
            script_log_dir: Directory containing log files
            log_files: List of log filenames
            max_count: Maximum number of log files to keep
    """
    if len(log_files) <= max_count:
        return

    # Sort by modification time (oldest first)
    log_files.sort(key=lambda x: os.path.getmtime(os.path.join(script_log_dir, x)))

    # Delete oldest files to keep only max_count
    to_delete = log_files[:-max_count]
    for filename in to_delete:
        os.remove(os.path.join(script_log_dir, filename))


def _rotate_by_age(script_log_dir, log_files, max_age_days):
    """Delete log files older than N days.

    Args:
            script_log_dir: Directory containing log files
            log_files: List of log filenames
            max_age_days: Maximum age of log files in days
    """
    cutoff = datetime.now() - timedelta(days=max_age_days)

    for filename in log_files:
        filepath = os.path.join(script_log_dir, filename)
        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))

        if file_time < cutoff:
            os.remove(filepath)


def get_latest_log(script_name):
    """Get the path to the latest log file for a script.

    Returns:
            tuple: (log_path, log_exists) where log_path is the path to the latest log
                   and log_exists is True if logs were found
    """
    script_log_dir = get_script_log_dir(script_name)

    if not os.path.exists(script_log_dir):
        return None, False

    log_files = os.listdir(script_log_dir)
    if not log_files:
        return None, False

    latest = max(log_files, key=lambda x: os.path.getmtime(os.path.join(script_log_dir, x)))
    return os.path.join(script_log_dir, latest), True


def read_log_content(log_path):
    """Read the content of a log file."""
    with open(log_path, "r") as f:
        return f.read()


def format_log_with_colors(content, show_colors=True):
    """Format log content with color coding.

    Returns:
            list: List of tuples (line_text, color) where color can be 'red', 'green', 'blue', or None
    """
    formatted_lines = []

    for line in content.split("\n"):
        color = None
        if show_colors:
            if "[ERROR]" in line or ("exit_code:" in line and "exit_code: 0" not in line):
                color = "red"
            elif "[SUCCESS]" in line or "exit_code: 0" in line:
                color = "green"
            elif "[START]" in line:
                color = "blue"

        formatted_lines.append((line, color))

    return formatted_lines


def get_log_history(script_name):
    """Get a list of all log files for a script with their timestamps.

    Returns:
            tuple: (log_files_info, history_exists) where log_files_info is a list of
                   tuples (filename, timestamp) sorted newest first
    """
    script_log_dir = get_script_log_dir(script_name)

    if not os.path.exists(script_log_dir):
        return [], False

    log_files = os.listdir(script_log_dir)
    if not log_files:
        return [], False

    # Sort by time, newest first
    log_files.sort(key=lambda x: os.path.getmtime(os.path.join(script_log_dir, x)), reverse=True)

    log_info = []
    for filename in log_files:
        mtime = os.path.getmtime(os.path.join(script_log_dir, filename))
        log_info.append((filename, mtime))

    return log_info, True


def clear_script_logs(script_name):
    """Clear all log files for a specific script.

    Returns:
            bool: True if logs were found and cleared, False otherwise
    """
    script_log_dir = get_script_log_dir(script_name)

    if not os.path.exists(script_log_dir):
        return False

    # Delete files but keep directory
    for filename in os.listdir(script_log_dir):
        filepath = os.path.join(script_log_dir, filename)
        if os.path.isfile(filepath):
            os.remove(filepath)

    return True


def clear_all_logs():
    """Clear all log files for all scripts.

    Returns:
            bool: True if log directory was found and cleared, False otherwise
    """
    log_dir = get_config_value("paths.log_dir", "logs")

    if not os.path.exists(log_dir):
        return False

    # Recursively delete files but keep directories
    for root, dirs, files in os.walk(log_dir):
        for filename in files:
            os.remove(os.path.join(root, filename))

    return True
