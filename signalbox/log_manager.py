# Log management functionality for signalbox

import os
import re
from datetime import datetime, timedelta
from .config import get_config_value
from .helpers import format_timestamp, get_resolved_log_dir, check_name, is_valid_name, parse_timestamp


def get_task_log_dir(task_name):
    """Get the log directory path for a task.

    Raises:
        ConfigurationError: If task_name could escape the log directory (e.g. contains '/' or '..')
    """
    return os.path.join(get_resolved_log_dir(), check_name(task_name))


def ensure_log_dir(task_name):
    """Ensure the log directory exists for a task."""
    os.makedirs(get_task_log_dir(task_name), exist_ok=True)


def get_log_path(task_name, timestamp=None):
    """Get the full path for a log file."""
    if timestamp is None:
        timestamp = format_timestamp(datetime.now())
    return os.path.join(get_task_log_dir(task_name), f"{timestamp}.log")


def _list_log_files(task_log_dir):
    """Return the names of execution log files in a task's log directory.

    The directory also holds the alerts/ subdirectory and a rotation lock file,
    so only regular files ending in .log count as logs.
    """
    return [f for f in os.listdir(task_log_dir) if f.endswith(".log") and os.path.isfile(os.path.join(task_log_dir, f))]


# Room set aside so an "OMITTED" marker cannot push the file over the limit.
_OMISSION_ALLOWANCE = 128

# Logs are always written as UTF-8, and the size cap is measured in the same
# encoding, so the budget counts bytes on disk rather than characters (a
# character can take up to 4 bytes). "replace" means output that cannot be
# encoded never stops the log from being written.
_LOG_ENCODING = "utf-8"
_LOG_ERRORS = "replace"

# Matches the markers _truncate_middle writes, plus the "[OUTPUT TRUNCATED"
# marker found in logs written by older versions.
_TRUNCATION_MARKER = re.compile(r"\[(OUTPUT|COMMAND|STDOUT|STDERR) (TRUNCATED|OMITTED)")


def _byte_len(text):
    """Size of `text` once written to a log file."""
    return len(text.encode(_LOG_ENCODING, _LOG_ERRORS))


def _head(data, size):
    """The first `size` bytes of `data`, dropping any character split at the cut."""
    return data[:size].decode(_LOG_ENCODING, "ignore")


def _tail(data, size):
    """The last `size` bytes of `data`, dropping any character split at the cut."""
    return data[-size:].decode(_LOG_ENCODING, "ignore") if size else ""


def _truncate_middle(text, budget, label):
    """Trim `text` to `budget` bytes, keeping the head and tail.

    The dropped middle is replaced by a marker saying how much was removed, so
    a truncated log never looks like complete output.
    """
    if not text:
        # Nothing to say: an empty stream needs no marker (and no budget).
        return ""
    if budget <= 0:
        return f"[{label} OMITTED - no room within log size limit]\n"
    data = text.encode(_LOG_ENCODING, _LOG_ERRORS)
    if len(data) <= budget:
        return text

    marker = f"\n\n[{label} TRUNCATED - {len(data) - budget} bytes removed]\n\n"
    if budget <= len(marker):
        # Not enough room for head/tail plus the full marker: keep a plain head,
        # but still flag it. The short marker comes out of _OMISSION_ALLOWANCE.
        return _head(data, budget) + f"\n[{label} TRUNCATED]\n"

    remaining = budget - len(marker)
    head = remaining // 2
    tail = remaining - head
    return _head(data, head) + marker + _tail(data, tail)


def _truncate_to_budget(command, return_code, stdout, stderr, max_log_size):
    """Fit the whole log entry inside max_log_size bytes.

    The budget covers the entire file, not each stream separately, and the
    command is trimmed too: an oversized command must not push the file past
    the limit that exists to stop runaway logs filling the disk.

    Returns:
        tuple: (command, stdout, stderr) trimmed to fit.
    """
    if max_log_size <= 0:
        return command, stdout, stderr

    # Reserve room for the omission markers themselves, so emitting one can
    # never push the file back over the limit.
    overhead = len(str(return_code)) + len("Command: \nReturn code: \nSTDOUT:\n\nSTDERR:\n\n") + _OMISSION_ALLOWANCE
    budget = max_log_size - overhead
    if budget <= 0:
        return "", "", ""

    # The command is metadata, so cap it at a modest share of the budget and
    # leave the rest for output.
    command_size = _byte_len(command)
    command = _truncate_middle(command, min(command_size, max(0, budget // 4)), "COMMAND")

    output_budget = budget - _byte_len(command)
    if output_budget <= 0:
        return command, "", ""

    # Split what is left between the two streams, giving each stream only what
    # it needs and letting the other use the slack.
    stdout_size = _byte_len(stdout)
    stderr_size = _byte_len(stderr)
    half = output_budget // 2
    if stdout_size <= half:
        stdout_budget = stdout_size
        stderr_budget = output_budget - stdout_budget
    elif stderr_size <= output_budget - half:
        stderr_budget = stderr_size
        stdout_budget = output_budget - stderr_budget
    else:
        stdout_budget = half
        stderr_budget = output_budget - half

    return (
        command,
        _truncate_middle(stdout, stdout_budget, "STDOUT"),
        _truncate_middle(stderr, stderr_budget, "STDERR"),
    )


def write_execution_log(log_file, command, return_code, stdout, stderr):
    """Write execution results to a log file.

    Args:
            log_file: Path to the log file
            command: The command that was executed
            return_code: Exit code from the command
            stdout: Standard output from the command
            stderr: Standard error from the command
    """
    # Check max log file size to prevent disk filling attacks.
    # Fallback matches the value in the shipped signalbox.yaml.
    # int(): a fractional setting such as 0.5 is valid but would otherwise make
    # every slice index below a float.
    max_log_size = int(get_config_value("logging.max_file_size_mb", 5) * 1024 * 1024)
    command, stdout, stderr = _truncate_to_budget(command, return_code, stdout, stderr, max_log_size)

    # Security: create file with 0o600 from the start so there is no window
    # between creation and chmod where the file could be world-readable.
    fd = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding=_LOG_ENCODING, errors=_LOG_ERRORS) as f:
        if get_config_value("logging.include_command", True):
            f.write(f"Command: {command}\n")

        if get_config_value("logging.include_return_code", True):
            f.write(f"Return code: {return_code}\n")

        if get_config_value("execution.capture_stdout", True):
            f.write("STDOUT:\n" + stdout + "\n")

        if get_config_value("execution.capture_stderr", True):
            f.write("STDERR:\n" + stderr + "\n")


def rotate_logs(task):
    """Rotate logs for a task based on configured limits.

    Supports three rotation types:
    - 'count': Keep only the N most recent log files
    - 'age': Delete log files older than N days
    - 'size': Keep the most recent logs whose combined size is at most N MB
      (the newest log is always kept)

    Args:
            task: Task configuration dict with optional 'log_limit' setting
    """
    import fcntl

    name = task["name"]
    task_log_dir = get_task_log_dir(name)

    if not os.path.exists(task_log_dir):
        return

    # Use file locking to prevent race conditions between concurrent executions.
    # The lock lives in the task's own log directory rather than the shared /tmp,
    # where a predictable name could be pre-created as a symlink by another user.
    lock_file = os.path.join(task_log_dir, ".rotate.lock")

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

            log_files = _list_log_files(task_log_dir)

            rotate = {"count": _rotate_by_count, "age": _rotate_by_age, "size": _rotate_by_size}.get(
                log_limit.get("type")
            )
            if rotate is None:
                raise ValueError(f"unknown log_limit type {log_limit.get('type')!r} (use count, age or size)")
            rotate(task_log_dir, log_files, log_limit["value"])

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


def _rotate_by_size(task_log_dir, log_files, max_size_mb):
    """Delete the oldest log files until the rest fit in max_size_mb (the newest is always kept).

    Args:
            task_log_dir: Directory containing log files
            log_files: List of log filenames
            max_size_mb: Maximum combined size of kept logs, in megabytes
    """
    max_bytes = max_size_mb * 1024 * 1024
    paths = sorted((os.path.join(task_log_dir, f) for f in log_files), key=os.path.getmtime, reverse=True)
    total = 0
    for index, path in enumerate(paths):
        total += os.path.getsize(path)
        if index > 0 and total > max_bytes:
            os.remove(path)


def get_latest_log(task_name):
    """Get the path to the latest log file for a task.

    Returns:
            tuple: (log_path, log_exists) where log_path is the path to the latest log
                   and log_exists is True if logs were found
    """
    task_log_dir = get_task_log_dir(task_name)

    if not os.path.exists(task_log_dir):
        return None, False

    log_files = _list_log_files(task_log_dir)
    if not log_files:
        return None, False

    latest = max(log_files, key=lambda x: os.path.getmtime(os.path.join(task_log_dir, x)))
    return os.path.join(task_log_dir, latest), True


def read_log_content(log_path):
    """Read the content of a log file."""
    with open(log_path, "r") as f:
        return f.read()


def format_log_with_colors(content, show_colors=True):
    """Format log content with color coding matching the format written by write_execution_log.

    Returns:
            list: List of tuples (line_text, color) where color can be 'red', 'green', 'blue', 'yellow' or None
    """
    formatted_lines = []

    for line in content.split("\n"):
        color = None
        if show_colors:
            if line.startswith("Return code: "):
                color = "green" if line == "Return code: 0" else "red"
            elif line.startswith("[TIMED OUT"):
                color = "red"
            elif _TRUNCATION_MARKER.match(line):
                color = "yellow"
            elif line.startswith("Command: ") or line in ("STDOUT:", "STDERR:"):
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

    log_files = _list_log_files(task_log_dir)
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
    """Clear execution logs and alert history for all tasks.

    Only removes *.log files and alerts/alerts.jsonl inside per-task
    directories, so a misconfigured paths.log_dir can't wipe unrelated files.

    Returns:
            bool: True if log directory was found and cleared, False otherwise
    """
    log_dir = get_resolved_log_dir()
    if not os.path.isdir(log_dir):
        return False

    for task_name in os.listdir(log_dir):
        task_log_dir = os.path.join(log_dir, task_name)
        if not is_valid_name(task_name) or not os.path.isdir(task_log_dir):
            continue
        for filename in _list_log_files(task_log_dir):
            os.remove(os.path.join(task_log_dir, filename))
        alert_log = os.path.join(task_log_dir, "alerts", "alerts.jsonl")
        if os.path.isfile(alert_log):
            os.remove(alert_log)

    return True


def get_all_log_files():
    """Get all log files from all tasks with metadata.

    Returns:
        list: List of dicts with task, log_file, timestamp, path
    """
    log_dir = get_resolved_log_dir()

    if not os.path.exists(log_dir):
        return []

    logs = []
    for task_name in os.listdir(log_dir):
        task_log_dir = os.path.join(log_dir, task_name)
        if not os.path.isdir(task_log_dir):
            continue

        for log_file in os.listdir(task_log_dir):
            if not log_file.endswith(".log"):
                continue

            log_path = os.path.join(task_log_dir, log_file)
            timestamp_str = log_file.replace(".log", "")

            # parse_timestamp returns None for names that don't match the configured
            # format (e.g. after logging.timestamp_format changes); fall back to mtime.
            timestamp = parse_timestamp(timestamp_str)
            if timestamp is None:
                timestamp = datetime.fromtimestamp(os.path.getmtime(log_path))

            logs.append(
                {
                    "task": task_name,
                    "log_file": log_file,
                    "timestamp": timestamp,
                    "timestamp_str": timestamp_str,
                    "path": log_path,
                    "mtime": os.path.getmtime(log_path),
                }
            )

    return logs


def parse_stdout_from_log(content):
    """Extract the STDOUT section from log file content."""
    marker = "STDOUT:\n"
    end_marker = "\nSTDERR:"
    start = content.find(marker)
    if start == -1:
        return ""
    start += len(marker)
    end = content.find(end_marker, start)
    return content[start:end].strip() if end != -1 else content[start:].strip()


def parse_stderr_from_log(content):
    """Extract the STDERR section from log file content."""
    marker = "STDERR:\n"
    start = content.find(marker)
    if start == -1:
        return ""
    return content[start + len(marker) :].strip()


def get_stdout_preview(content, max_chars=70):
    """Return a single-line preview of stdout.

    Prefers the first substantive line (not a bare label ending in ':').
    Falls back to the first non-empty line if everything looks like a label.
    """
    first_nonempty = None
    for line in parse_stdout_from_log(content).splitlines():
        line = line.strip()
        if not line:
            continue
        if first_nonempty is None:
            first_nonempty = line
        if not line.endswith(":"):
            return line[:max_chars] + ("…" if len(line) > max_chars else "")
    if first_nonempty:
        return first_nonempty[:max_chars] + ("…" if len(first_nonempty) > max_chars else "")
    return ""


def parse_log_metadata(log_path):
    """Parse log file to extract status and metadata.

    Args:
        log_path: Path to log file

    Returns:
        dict: Metadata including status, return_code, stdout_preview
    """
    metadata = {
        "status": "unknown",
        "return_code": None,
        "command": None,
        "stdout_preview": "",
    }

    if not os.path.exists(log_path):
        return metadata

    try:
        with open(log_path, "r") as f:
            content = f.read()

        for line in content.split("\n"):
            if line.startswith("Return code: "):
                try:
                    metadata["return_code"] = int(line.split(": ")[1])
                    metadata["status"] = "success" if metadata["return_code"] == 0 else "failed"
                except Exception:
                    pass
                break

        for line in content.split("\n"):
            if line.startswith("Command: "):
                metadata["command"] = line.split(": ", 1)[1]
                break

        metadata["stdout_preview"] = get_stdout_preview(content)

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
        filtered = [entry for entry in filtered if entry["task"] == task]

    if since:
        filtered = [entry for entry in filtered if entry["timestamp"] >= since]

    if until:
        filtered = [entry for entry in filtered if entry["timestamp"] <= until]

    # Sort by timestamp descending (newest first) before reading any files, so
    # only as many logs as `limit` needs are opened and parsed.
    filtered = sorted(filtered, key=lambda x: x["timestamp"], reverse=True)

    selected = []
    for log_entry in filtered:
        if limit and len(selected) >= limit:
            break
        log_entry["metadata"] = parse_log_metadata(log_entry["path"])
        if status and log_entry["metadata"]["status"] != status:
            continue
        selected.append(log_entry)
    filtered = selected

    return filtered
