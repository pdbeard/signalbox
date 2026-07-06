# Runtime state management for signalbox
import os
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


def save_task_runtime_state(task_name, source_file, last_run, last_status):
    """Save runtime state for a task to the appropriate runtime file."""
    config_filename = os.path.basename(source_file)
    config_basename = os.path.splitext(config_filename)[0]
    runtime_filename = f"runtime_{config_basename}.yaml"
    runtime_filepath = resolve_path(os.path.join("runtime/tasks", runtime_filename))
    runtime_data = {"tasks": {}}
    if os.path.exists(runtime_filepath):
        try:
            with open(runtime_filepath, "r") as f:
                runtime_data = yaml.safe_load(f) or {"tasks": {}}
        except Exception:
            runtime_data = {"tasks": {}}
    if "tasks" not in runtime_data:
        runtime_data["tasks"] = {}
    runtime_data["tasks"][task_name] = {"last_run": last_run, "last_status": last_status}
    os.makedirs(os.path.dirname(runtime_filepath), exist_ok=True)
    with open(runtime_filepath, "w") as f:
        f.write(f"# Runtime state for {config_filename} - auto-generated, do not edit manually\n")
        yaml.dump(runtime_data, f, default_flow_style=False, sort_keys=False)


def save_group_runtime_state(
    group_name, source_file, last_run, last_status, execution_time, tasks_total, tasks_successful
):
    """Save runtime state for a group to the appropriate runtime file."""
    config_filename = os.path.basename(source_file)
    config_basename = os.path.splitext(config_filename)[0]
    runtime_filename = f"runtime_{config_basename}.yaml"
    runtime_filepath = resolve_path(os.path.join("runtime/groups", runtime_filename))
    runtime_data = {"groups": {}}
    if os.path.exists(runtime_filepath):
        try:
            with open(runtime_filepath, "r") as f:
                runtime_data = yaml.safe_load(f) or {"groups": {}}
        except Exception:
            runtime_data = {"groups": {}}
    if "groups" not in runtime_data:
        runtime_data["groups"] = {}
    prev_state = runtime_data["groups"].get(group_name, {})
    execution_count = prev_state.get("execution_count", 0) + 1
    runtime_data["groups"][group_name] = {
        "last_run": last_run,
        "last_status": last_status,
        "execution_time_seconds": execution_time,
        "execution_count": execution_count,
        "tasks_total": tasks_total,
        "tasks_successful": tasks_successful,
        "success_rate": round((tasks_successful / tasks_total * 100), 1) if tasks_total > 0 else 0.0,
    }
    os.makedirs(os.path.dirname(runtime_filepath), exist_ok=True)
    with open(runtime_filepath, "w") as f:
        f.write(f"# Runtime state for {config_filename} - auto-generated, do not edit manually\n")
        yaml.dump(runtime_data, f, default_flow_style=False, sort_keys=False)


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
