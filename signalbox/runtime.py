# Runtime state management for signalbox
import fcntl
import os
import tempfile

import yaml
from .config import resolve_path
from .helpers import load_yaml_dict_from_dir


def load_runtime_state():
    """Load runtime state (last_run, last_status) from runtime directory."""
    runtime_state = {"tasks": {}, "groups": {}}

    # Load task runtime state
    runtime_tasks_dir = resolve_path("runtime/tasks")
    runtime_state["tasks"] = load_yaml_dict_from_dir(runtime_tasks_dir, "tasks", filename_prefix="runtime_")

    # Load group runtime state
    runtime_groups_dir = resolve_path("runtime/groups")
    runtime_state["groups"] = load_yaml_dict_from_dir(runtime_groups_dir, "groups", filename_prefix="runtime_")

    return runtime_state


def _update_runtime_file(runtime_dir, source_file, section, update):
    """Apply update(section_dict) to a runtime state file under an exclusive lock.

    Tasks from the same config file share one runtime file, and parallel groups
    update it from several threads at once. The flock serializes the
    read-modify-write so no update is lost, and the temp-file + rename keeps
    readers (e.g. the tray app) from ever seeing a half-written file.
    """
    config_filename = os.path.basename(source_file)
    config_basename = os.path.splitext(config_filename)[0]
    runtime_filepath = resolve_path(os.path.join(runtime_dir, f"runtime_{config_basename}.yaml"))
    directory = os.path.dirname(runtime_filepath)
    os.makedirs(directory, exist_ok=True)

    # Dotfile so load_yaml_dict_from_dir skips it
    lock_path = os.path.join(directory, f".runtime_{config_basename}.lock")
    with open(lock_path, "w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)

        runtime_data = {}
        if os.path.exists(runtime_filepath):
            try:
                with open(runtime_filepath, "r") as f:
                    runtime_data = yaml.safe_load(f) or {}
            except Exception:
                runtime_data = {}
        if not isinstance(runtime_data.get(section), dict):
            runtime_data[section] = {}
        update(runtime_data[section])

        fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".runtime_", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(f"# Runtime state for {config_filename} - auto-generated, do not edit manually\n")
                yaml.dump(runtime_data, f, default_flow_style=False, sort_keys=False)
            os.replace(tmp_path, runtime_filepath)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def save_task_runtime_state(task_name, source_file, last_run, last_status):
    """Save runtime state for a task to the appropriate runtime file."""

    def update(tasks):
        tasks[task_name] = {"last_run": last_run, "last_status": last_status}

    _update_runtime_file("runtime/tasks", source_file, "tasks", update)


def save_group_runtime_state(
    group_name, source_file, last_run, last_status, execution_time, tasks_total, tasks_successful
):
    """Save runtime state for a group to the appropriate runtime file."""

    def update(groups):
        prev_state = groups.get(group_name, {})
        groups[group_name] = {
            "last_run": last_run,
            "last_status": last_status,
            "execution_time_seconds": execution_time,
            "execution_count": prev_state.get("execution_count", 0) + 1,
            "tasks_total": tasks_total,
            "tasks_successful": tasks_successful,
            "success_rate": round((tasks_successful / tasks_total * 100), 1) if tasks_total > 0 else 0.0,
        }

    _update_runtime_file("runtime/groups", source_file, "groups", update)


def merge_config_with_runtime_state(config, runtime_state):
    """Merge user configuration with runtime state."""
    for task in config["tasks"]:
        task_name = task["name"]
        if task_name in runtime_state["tasks"]:
            runtime_info = runtime_state["tasks"][task_name]
            task["last_run"] = runtime_info.get("last_run", "")
            task["last_status"] = runtime_info.get("last_status", "no logs")
        else:
            task["last_run"] = ""
            task["last_status"] = "no logs"
    for group in config["groups"]:
        group_name = group["name"]
        if group_name in runtime_state["groups"]:
            runtime_info = runtime_state["groups"][group_name]
            # Add any group-level runtime state here in the future
    return config


def filter_runtime_to_config(runtime_state, config):
    """Return runtime_state restricted to tasks/groups that still exist in config.

    Runtime files keep entries for deleted or renamed tasks; without this a
    task that was removed after failing would keep the tray red forever.
    Nothing is deleted, so a temporarily broken config file loses no history.
    """
    task_names = {t.get("name") for t in config.get("tasks", []) if isinstance(t, dict)}
    group_names = {g.get("name") for g in config.get("groups", []) if isinstance(g, dict)}
    return {
        "tasks": {k: v for k, v in runtime_state.get("tasks", {}).items() if k in task_names},
        "groups": {k: v for k, v in runtime_state.get("groups", {}).items() if k in group_names},
    }
