# Runtime state management for signalbox
import os
import yaml
import click
from .config import resolve_path


def load_runtime_state():
    """Load runtime state (last_run, last_status) from runtime directory."""
    runtime_state = {"scripts": {}, "groups": {}}
    runtime_scripts_dir = resolve_path("runtime/scripts")
    if os.path.exists(runtime_scripts_dir):
        for filename in os.listdir(runtime_scripts_dir):
            if filename.startswith("runtime_") and filename.endswith(".yaml"):
                filepath = os.path.join(runtime_scripts_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        data = yaml.safe_load(f)
                        if data and "scripts" in data:
                            runtime_state["scripts"].update(data["scripts"])
                except Exception as e:
                    click.echo(f"Warning: Failed to load runtime state {filepath}: {e}", err=True)
    runtime_groups_dir = resolve_path("runtime/groups")
    if os.path.exists(runtime_groups_dir):
        for filename in os.listdir(runtime_groups_dir):
            if filename.startswith("runtime_") and filename.endswith(".yaml"):
                filepath = os.path.join(runtime_groups_dir, filename)
                try:
                    with open(filepath, "r") as f:
                        data = yaml.safe_load(f)
                        if data and "groups" in data:
                            runtime_state["groups"].update(data["groups"])
                except Exception as e:
                    click.echo(f"Warning: Failed to load runtime state {filepath}: {e}", err=True)
    return runtime_state


def save_script_runtime_state(script_name, source_file, last_run, last_status):
    """Save runtime state for a script to the appropriate runtime file."""
    config_filename = os.path.basename(source_file)
    config_basename = os.path.splitext(config_filename)[0]
    runtime_filename = f"runtime_{config_basename}.yaml"
    runtime_filepath = resolve_path(os.path.join("runtime/scripts", runtime_filename))
    runtime_data = {"scripts": {}}
    if os.path.exists(runtime_filepath):
        try:
            with open(runtime_filepath, "r") as f:
                runtime_data = yaml.safe_load(f) or {"scripts": {}}
        except Exception:
            runtime_data = {"scripts": {}}
    if "scripts" not in runtime_data:
        runtime_data["scripts"] = {}
    runtime_data["scripts"][script_name] = {"last_run": last_run, "last_status": last_status}
    os.makedirs(os.path.dirname(runtime_filepath), exist_ok=True)
    with open(runtime_filepath, "w") as f:
        f.write(f"# Runtime state for {config_filename} - auto-generated, do not edit manually\n")
        yaml.dump(runtime_data, f, default_flow_style=False, sort_keys=False)


def save_group_runtime_state(
    group_name, source_file, last_run, last_status, execution_time, scripts_total, scripts_successful
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
        "scripts_total": scripts_total,
        "scripts_successful": scripts_successful,
        "success_rate": round((scripts_successful / scripts_total * 100), 1) if scripts_total > 0 else 0.0,
    }
    os.makedirs(os.path.dirname(runtime_filepath), exist_ok=True)
    with open(runtime_filepath, "w") as f:
        f.write(f"# Runtime state for {config_filename} - auto-generated, do not edit manually\n")
        yaml.dump(runtime_data, f, default_flow_style=False, sort_keys=False)


def merge_config_with_runtime_state(config, runtime_state):
    """Merge user configuration with runtime state."""
    for script in config["scripts"]:
        script_name = script["name"]
        if script_name in runtime_state["scripts"]:
            runtime_info = runtime_state["scripts"][script_name]
            script["last_run"] = runtime_info.get("last_run", "")
            script["last_status"] = runtime_info.get("last_status", "not run")
        else:
            script["last_run"] = ""
            script["last_status"] = "not run"
    for group in config["groups"]:
        group_name = group["name"]
        if group_name in runtime_state["groups"]:
            runtime_info = runtime_state["groups"][group_name]
            # Add any group-level runtime state here in the future
    return config
