# Log management functionality for signalbox

import os
from datetime import datetime, timedelta
from .config import get_config_value
from .helpers import format_timestamp



def get_task_log_dir(task_name):
    """Get the log directory path for a task."""
    log_dir = get_config_value("paths.log_dir", "logs")
    return os.path.join(log_dir, task_name)



def ensure_log_dir(task_name):
    """Ensure the log directory exists for a task."""
    task_log_dir = get_task_log_dir(task_name)
    if not os.path.exists(task_log_dir):
        os.makedirs(task_log_dir)



def get_log_path(task_name, timestamp=None):
    """Get the full path for a log file.

    Args:
        task_name: Name of the task
        timestamp: Optional timestamp string, defaults to current time

    Returns:
        str: Full path to the log file
    """
    if timestamp is None:
        timestamp = format_timestamp(datetime.now())

    log_dir = get_config_value("paths.log_dir", "logs")
    return os.path.join(log_dir, task_name, f"{timestamp}.log")


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


def rotate_logs(task):
    """Rotate logs for a task based on configured limits.

    Supports two rotation types:
    - 'count': Keep only the N most recent log files
    - 'age': Delete log files older than N days

    Args:
            task: Task configuration dict with optional 'log_limit' setting
    """
    import fcntl
    import tempfile

    name = task["name"]
    task_log_dir = get_task_log_dir(name)

    if not os.path.exists(task_log_dir):
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
            log_limit = task.get("log_limit", default_limit)

            log_files = os.listdir(task_log_dir)

            if log_limit["type"] == "count":
                _rotate_by_count(task_log_dir, log_files, log_limit["value"])
            elif log_limit["type"] == "age":
                _rotate_by_age(task_log_dir, log_files, log_limit["value"])

            # Lock is automatically released when file is closed
    except Exception as e:
        # Don't fail the entire task execution if rotation fails
        import click

        click.echo(f"Warning: Log rotation failed for {name}: {e}", err=True)


def _rotate_by_count(task_log_dir, log_files, max_count):
    """Keep only the most recent N log files.

    Args:
            task_log_dir: Directory containing log files
            log_files: List of log filenames
            max_count: Maximum number of log files to keep
    """
    if len(log_files) <= max_count:
        return

    # Sort by modification time (oldest first)
    log_files.sort(key=lambda x: os.path.getmtime(os.path.join(task_log_dir, x)))

    # Delete oldest files to keep only max_count
    to_delete = log_files[:-max_count]
    for filename in to_delete:
        os.remove(os.path.join(task_log_dir, filename))


def _rotate_by_age(task_log_dir, log_files, max_age_days):
    """Delete log files older than N days.

    Args:
            task_log_dir: Directory containing log files
            log_files: List of log filenames
            max_age_days: Maximum age of log files in days
    """
    cutoff = datetime.now() - timedelta(days=max_age_days)

    for filename in log_files:
        filepath = os.path.join(task_log_dir, filename)
        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))

        if file_time < cutoff:
            os.remove(filepath)


def get_latest_log(task_name):
    """Get the path to the latest log file for a task.

    Returns:
            tuple: (log_path, log_exists) where log_path is the path to the latest log
                   and log_exists is True if logs were found
    """
    task_log_dir = get_task_log_dir(task_name)

    if not os.path.exists(task_log_dir):
        return None, False

    log_files = os.listdir(task_log_dir)
    if not log_files:
        return None, False

    latest = max(log_files, key=lambda x: os.path.getmtime(os.path.join(task_log_dir, x)))
    return os.path.join(task_log_dir, latest), True


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


def get_log_history(task_name):
    """Get a list of all log files for a task with their timestamps.

    Returns:
            tuple: (log_files_info, history_exists) where log_files_info is a list of
                   tuples (filename, timestamp) sorted newest first
    """
    task_log_dir = get_task_log_dir(task_name)

    if not os.path.exists(task_log_dir):
        return [], False

    log_files = os.listdir(task_log_dir)
    if not log_files:
        return [], False

    # Sort by time, newest first
    log_files.sort(key=lambda x: os.path.getmtime(os.path.join(task_log_dir, x)), reverse=True)

    log_info = []
    for filename in log_files:
        mtime = os.path.getmtime(os.path.join(task_log_dir, filename))
        log_info.append((filename, mtime))

    return log_info, True


def clear_task_logs(task_name):
    """Clear all log files for a specific task.

    Returns:
            bool: True if logs were found and cleared, False otherwise
    """
    task_log_dir = get_task_log_dir(task_name)

    if not os.path.exists(task_log_dir):
        return False

    # Delete files but keep directory
    for filename in os.listdir(task_log_dir):
        filepath = os.path.join(task_log_dir, filename)
        if os.path.isfile(filepath):
            os.remove(filepath)

    return True


def clear_all_logs():
    """Clear all log files for all tasks.

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


def get_all_log_files():
    """Get all log files from all tasks with metadata.
    
    Returns:
        list: List of dicts with task, log_file, timestamp, path
    """
    from .helpers import parse_timestamp
    log_dir = get_config_value("paths.log_dir", "logs")
    
    if not os.path.exists(log_dir):
        return []
    
    logs = []
    for task_name in os.listdir(log_dir):
        task_log_dir = os.path.join(log_dir, task_name)
        if not os.path.isdir(task_log_dir):
            continue
            
        for log_file in os.listdir(task_log_dir):
            if not log_file.endswith('.log'):
                continue
                
            log_path = os.path.join(task_log_dir, log_file)
            timestamp_str = log_file.replace('.log', '')
            
            try:
                timestamp = parse_timestamp(timestamp_str)
            except:
                timestamp = datetime.fromtimestamp(os.path.getmtime(log_path))
            
            logs.append({
                'task': task_name,
                'log_file': log_file,
                'timestamp': timestamp,
                'timestamp_str': timestamp_str,
                'path': log_path,
                'mtime': os.path.getmtime(log_path)
            })
    
    return logs


def parse_log_metadata(log_path):
    """Parse log file to extract status and metadata.
    
    Args:
        log_path: Path to log file
        
    Returns:
        dict: Metadata including status, return_code, duration (if available)
    """
    metadata = {
        'status': 'unknown',
        'return_code': None,
        'duration': None,
        'command': None
    }
    
    if not os.path.exists(log_path):
        return metadata
    
    try:
        with open(log_path, 'r') as f:
            content = f.read()
            
        # Parse return code
        if 'Return code: ' in content:
            for line in content.split('\n'):
                if line.startswith('Return code: '):
                    try:
                        metadata['return_code'] = int(line.split(': ')[1])
                        metadata['status'] = 'success' if metadata['return_code'] == 0 else 'failed'
                    except:
                        pass
                    break
        
        # Parse command
        if 'Command: ' in content:
            for line in content.split('\n'):
                if line.startswith('Command: '):
                    metadata['command'] = line.split(': ', 1)[1]
                    break
                    
    except Exception:
        pass
    
    return metadata


def filter_logs(logs, task=None, status=None, since=None, until=None, limit=None):
    """Filter log entries based on criteria.
    
    Args:
        logs: List of log entries
        task: Filter to specific task name
        status: Filter by status (success, failed)
        since: datetime - show logs since this time
        until: datetime - show logs until this time
        limit: Maximum number of logs to return
        
    Returns:
        list: Filtered log entries
    """
    filtered = logs
    
    if task:
        filtered = [l for l in filtered if l['task'] == task]
    
    if since:
        filtered = [l for l in filtered if l['timestamp'] >= since]
    
    if until:
        filtered = [l for l in filtered if l['timestamp'] <= until]
    
    if status:
        # Need to parse each log to check status
        filtered_with_status = []
        for log_entry in filtered:
            metadata = parse_log_metadata(log_entry['path'])
            log_entry['metadata'] = metadata
            if metadata['status'] == status:
                filtered_with_status.append(log_entry)
        filtered = filtered_with_status
    else:
        # Add metadata to all logs
        for log_entry in filtered:
            log_entry['metadata'] = parse_log_metadata(log_entry['path'])
    
    # Sort by timestamp descending (newest first)
    filtered.sort(key=lambda x: x['timestamp'], reverse=True)
    
    if limit:
        filtered = filtered[:limit]
    
    return filtered
