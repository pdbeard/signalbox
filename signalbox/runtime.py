# Runtime state management for signalbox
import fcntl
import json
import os
import tempfile

import yaml
from .config import resolve_path, get_config_value
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


def save_task_runtime_state(task_name, source_file, last_run, last_status, skip_reason=None):
    """Save runtime state for a task to the appropriate runtime file.

    A skipped run also records why, and how many runs in a row were skipped
    (the tray warns after execution.skip_warn_after); any real run resets that count.
    """

    def update(tasks):
        entry = {"last_run": last_run, "last_status": last_status}
        if last_status == "skipped":
            previous = tasks.get(task_name)
            previous_count = previous.get("consecutive_skips", 0) if isinstance(previous, dict) else 0
            entry["skip_reason"] = skip_reason or ""
            entry["consecutive_skips"] = (previous_count if isinstance(previous_count, int) else 0) + 1
        tasks[task_name] = entry

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
        if not isinstance(task, dict):
            continue  # reported by `signalbox validate`; must not break listing the rest
        task_name = task.get("name")
        if task_name in runtime_state["tasks"]:
            runtime_info = runtime_state["tasks"][task_name]
            task["last_run"] = runtime_info.get("last_run", "")
            task["last_status"] = runtime_info.get("last_status", "never run")
        else:
            task["last_run"] = ""
            task["last_status"] = "never run"
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


TRAY_STATE_FILE = "runtime/tray_state.json"
LEGACY_TRAY_STATE_FILE = "~/.signalbox_tray_state.json"


def load_tray_state():
    """Load the tray's own settings (ignore_failures_before, menu toggles).

    Kept out of signalbox.yaml so the tray never rewrites (and strips the
    comments from) the user's config file. The old
    ~/.signalbox_tray_state.json is still read if no new file exists yet.
    """
    for state_file in (resolve_path(TRAY_STATE_FILE), os.path.expanduser(LEGACY_TRAY_STATE_FILE)):
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def save_tray_state(state):
    """Save the tray's settings atomically."""
    state_file = resolve_path(TRAY_STATE_FILE)
    state_dir = os.path.dirname(state_file)
    os.makedirs(state_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=state_dir, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        os.replace(tmp_path, state_file)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def set_tray_setting(key, value):
    """Store one value in the tray state file, keeping the others."""
    state = load_tray_state()
    state[key] = value
    save_tray_state(state)


def setting_with_tray_override(key, default):
    """A signalbox.yaml setting, unless the tray menu has switched it (stored in the tray state)."""
    return load_tray_state().get(key, get_config_value(key, default))
