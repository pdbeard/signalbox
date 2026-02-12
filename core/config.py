# Configuration management for signalbox
import os
import yaml
from .helpers import load_yaml_files_from_dir

CONFIG_FILE = "config/signalbox.yaml"
TASKS_FILE = "tasks.yaml"
GROUPS_FILE = "groups.yaml"


class ConfigManager:
    """
    Configuration manager for signalbox.

    Replaces module-level globals with a proper class-based approach.
    Benefits:
    - Better testability (can create independent instances)
    - Thread-safe (each thread can have its own instance)
    - Explicit state management (no hidden globals)
    - Easy to reset/reload configuration
    """

    def __init__(self, config_home=None):
        """
        Initialize configuration manager.

        Args:
                config_home: Override config home directory (useful for testing)
        """
        self._config_home = config_home
        self._global_config = None

    def find_config_home(self):
        """
        Find the signalbox configuration directory.
        Priority order:
        1. Constructor override (if provided)
        2. SIGNALBOX_HOME environment variable
        3. XDG_CONFIG_HOME/signalbox if XDG_CONFIG_HOME is set
        4. ~/.config/signalbox (if it exists and has config)
        5. Current working directory (if config/signalbox.yaml exists locally)
        6. ~/.config/signalbox (final fallback for init)
        """
        if self._config_home is not None:
            return self._config_home

        # 1. SIGNALBOX_HOME
        env_home = os.environ.get("SIGNALBOX_HOME")
        if env_home:
            env_home = os.path.expanduser(env_home)
            self._config_home = env_home
            return self._config_home

        # 2. XDG_CONFIG_HOME
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            xdg_path = os.path.expanduser(os.path.join(xdg_config_home, "signalbox"))
            if os.path.isdir(xdg_path) and os.path.exists(os.path.join(xdg_path, "config/signalbox.yaml")):
                self._config_home = xdg_path
                return self._config_home
            # If directory doesn't exist, still use as preferred location for init
            self._config_home = xdg_path
            return self._config_home

        # 3. ~/.config/signalbox (if it exists with config)
        user_config = os.path.expanduser("~/.config/signalbox")
        if os.path.isdir(user_config) and os.path.exists(os.path.join(user_config, "config/signalbox.yaml")):
            self._config_home = user_config
            return self._config_home

        # 4. Current directory (for development/project-specific configs)
        cwd = os.getcwd()
        if os.path.exists(os.path.join(cwd, "config/signalbox.yaml")):
            self._config_home = cwd
            return self._config_home

        # 5. Final fallback: use ~/.config/signalbox (for init command)
        self._config_home = user_config
        return self._config_home

    def resolve_path(self, path):
        """Resolve a path relative to config home if it's not absolute."""
        if os.path.isabs(path):
            return path
        config_home = self.find_config_home()
        return os.path.join(config_home, path)

    def load_global_config(self):
        """Load global configuration settings from config/signalbox.yaml."""
        if self._global_config is None:
            config_file = self.resolve_path(CONFIG_FILE)
            if os.path.exists(config_file):
                with open(config_file, "r") as f:
                    self._global_config = yaml.safe_load(f) or {}
            else:
                self._global_config = {}
        return self._global_config

    def get_config_value(self, path, default=None):
        """Get a configuration value using dot notation (e.g., 'execution.default_timeout')."""
        config = self.load_global_config()
        keys = path.split(".")
        value = config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def load_config(self, suppress_warnings=False):

        """Load configuration from tasks and groups directories."""
        config = {"tasks": [], "groups": [], "_task_sources": {}, "_group_sources": {}}


        # Load user tasks from directory (only 'tasks_file' config key supported)
        user_tasks_dir = self.get_config_value("paths.tasks_file", TASKS_FILE)
        user_tasks_dir = self.resolve_path(user_tasks_dir)
        if os.path.isdir(user_tasks_dir):
            tasks_list = load_yaml_files_from_dir(
                user_tasks_dir, key="tasks", track_sources=True, suppress_warnings=suppress_warnings
            )
            for item in tasks_list:
                task_name = item["data"].get("name")
                if task_name:
                    config["_task_sources"][task_name] = item["source"]
                config["tasks"].append(item["data"])

        # Load catalog tasks if enabled
        include_catalog = self.get_config_value("include_catalog", True)
        if include_catalog:
            catalog_tasks_path = self.get_config_value("paths.catalog_tasks_file", "config/catalog/tasks")
            catalog_tasks_path = self.resolve_path(catalog_tasks_path)
            if os.path.isdir(catalog_tasks_path):
                catalog_tasks_list = load_yaml_files_from_dir(
                    catalog_tasks_path, key="tasks", track_sources=True, suppress_warnings=suppress_warnings
                )
                for item in catalog_tasks_list:
                    task_name = item["data"].get("name")
                    if task_name:
                        config["_task_sources"][task_name] = item["source"]
                    config["tasks"].append(item["data"])

        # Load user groups from directory
        groups_path = self.get_config_value("paths.groups_file", GROUPS_FILE)
        groups_path = self.resolve_path(groups_path)
        if os.path.isdir(groups_path):
            groups_list = load_yaml_files_from_dir(
                groups_path, key="groups", track_sources=True, suppress_warnings=suppress_warnings
            )
            for item in groups_list:
                group_name = item["data"].get("name")
                if group_name:
                    config["_group_sources"][group_name] = item["source"]
                config["groups"].append(item["data"])

        # Load catalog groups if enabled
        if include_catalog:
            catalog_groups_path = self.get_config_value("paths.catalog_groups_file", "config/catalog/groups")
            catalog_groups_path = self.resolve_path(catalog_groups_path)
            if os.path.isdir(catalog_groups_path):
                catalog_groups_list = load_yaml_files_from_dir(
                    catalog_groups_path, key="groups", track_sources=True, suppress_warnings=suppress_warnings
                )
                for item in catalog_groups_list:
                    group_name = item["data"].get("name")
                    if group_name:
                        config["_group_sources"][group_name] = item["source"]
                    config["groups"].append(item["data"])

        # Note: runtime state merging should be handled in runtime.py
        return config

    def save_config(self, config):
        """Save configuration back to original source files."""
        tasks_path = self.get_config_value("paths.tasks_file", TASKS_FILE)
        tasks_path = self.resolve_path(tasks_path)
        task_sources = config.get("_task_sources", {})
        if "tasks" in config and os.path.isdir(tasks_path):
            files_to_save = {}
            for task in config["tasks"]:
                task_name = task.get("name")
                source_file = task_sources.get(task_name)
                if source_file and os.path.exists(source_file):
                    if source_file not in files_to_save:
                        files_to_save[source_file] = []
                    files_to_save[source_file].append(task)
                else:
                    new_file = os.path.join(tasks_path, "_new.yaml")
                    if new_file not in files_to_save:
                        files_to_save[new_file] = []
                    files_to_save[new_file].append(task)
            for filepath, tasks in files_to_save.items():
                with open(filepath, "w") as f:
                    yaml.dump({"tasks": tasks}, f, default_flow_style=False, sort_keys=False)
        if "groups" in config:
            groups_path = self.get_config_value("paths.groups_file", GROUPS_FILE)
            groups_path = self.resolve_path(groups_path)
            group_sources = config.get("_group_sources", {})
            if os.path.isdir(groups_path):
                files_to_save = {}
                for group in config["groups"]:
                    group_name = group.get("name")
                    source_file = group_sources.get(group_name)
                    if source_file and os.path.exists(source_file):
                        if source_file not in files_to_save:
                            files_to_save[source_file] = []
                        files_to_save[source_file].append(group)
                    else:
                        new_file = os.path.join(groups_path, "_new.yaml")
                        if new_file not in files_to_save:
                            files_to_save[new_file] = []
                        files_to_save[new_file].append(group)
                for filepath, groups in files_to_save.items():
                    with open(filepath, "w") as f:
                        yaml.dump({"groups": groups}, f, default_flow_style=False, sort_keys=False)

    def reset(self):
        """Reset cached configuration (useful for testing or reload)."""
        self._global_config = None
        self._config_home = None


# Global instance for backward compatibility
# Modules can use this default instance or create their own
_default_config_manager = ConfigManager()


# Convenience functions that use the default instance
# These maintain backward compatibility with existing code
def find_config_home():
    """Find the signalbox configuration directory."""
    return _default_config_manager.find_config_home()


def resolve_path(path):
    """Resolve a path relative to config home if it's not absolute."""
    return _default_config_manager.resolve_path(path)


def load_global_config():
    """Load global configuration settings from config/signalbox.yaml."""
    return _default_config_manager.load_global_config()


def get_config_value(path, default=None):
    """Get a configuration value using dot notation (e.g., 'execution.default_timeout')."""
    return _default_config_manager.get_config_value(path, default)


def load_config(suppress_warnings=False):
    """Load configuration from tasks and groups directories."""
    return _default_config_manager.load_config(suppress_warnings=suppress_warnings)


def save_config(config):
    """Save configuration back to original source files."""
    return _default_config_manager.save_config(config)


def reset_config():
    """Reset the default configuration manager (useful for testing)."""
    _default_config_manager.reset()
