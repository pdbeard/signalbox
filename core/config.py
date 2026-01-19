# Configuration management for signalbox
import os
import yaml
import click
from .helpers import load_yaml_files_from_dir

CONFIG_FILE = "config/signalbox.yaml"
SCRIPTS_FILE = "scripts.yaml"
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
        3. ~/.config/signalbox/ if it exists
        4. Current working directory
        """
        if self._config_home is not None:
            return self._config_home

        # Check SIGNALBOX_HOME environment variable
        env_home = os.environ.get("SIGNALBOX_HOME")
        if env_home:
            env_home = os.path.expanduser(env_home)
            if os.path.isdir(env_home):
                self._config_home = env_home
                return self._config_home

        # Check ~/.config/signalbox/
        user_config = os.path.expanduser("~/.config/signalbox")
        if os.path.isdir(user_config) and os.path.exists(os.path.join(user_config, "config/signalbox.yaml")):
            self._config_home = user_config
            return self._config_home

        # Fall back to current working directory
        self._config_home = os.getcwd()
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
        """Load configuration from scripts and groups directories."""
        config = {"scripts": [], "groups": [], "_script_sources": {}, "_group_sources": {}}
        
        # Load user scripts from directory
        scripts_path = self.get_config_value("paths.scripts_file", SCRIPTS_FILE)
        scripts_path = self.resolve_path(scripts_path)
        if os.path.isdir(scripts_path):
            scripts_list = load_yaml_files_from_dir(scripts_path, key="scripts", track_sources=True, suppress_warnings=suppress_warnings)
            for item in scripts_list:
                script_name = item["data"].get("name")
                if script_name:
                    config["_script_sources"][script_name] = item["source"]
                config["scripts"].append(item["data"])
        
        # Load catalog scripts if enabled
        include_catalog = self.get_config_value("include_catalog", True)
        if include_catalog:
            catalog_scripts_path = self.get_config_value("paths.catalog_scripts_file", "config/catalog/scripts")
            catalog_scripts_path = self.resolve_path(catalog_scripts_path)
            if os.path.isdir(catalog_scripts_path):
                catalog_scripts_list = load_yaml_files_from_dir(catalog_scripts_path, key="scripts", track_sources=True, suppress_warnings=suppress_warnings)
                for item in catalog_scripts_list:
                    script_name = item["data"].get("name")
                    if script_name:
                        config["_script_sources"][script_name] = item["source"]
                    config["scripts"].append(item["data"])
        
        # Load user groups from directory
        groups_path = self.get_config_value("paths.groups_file", GROUPS_FILE)
        groups_path = self.resolve_path(groups_path)
        if os.path.isdir(groups_path):
            groups_list = load_yaml_files_from_dir(groups_path, key="groups", track_sources=True, suppress_warnings=suppress_warnings)
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
                catalog_groups_list = load_yaml_files_from_dir(catalog_groups_path, key="groups", track_sources=True, suppress_warnings=suppress_warnings)
                for item in catalog_groups_list:
                    group_name = item["data"].get("name")
                    if group_name:
                        config["_group_sources"][group_name] = item["source"]
                    config["groups"].append(item["data"])
        
        # Note: runtime state merging should be handled in runtime.py
        return config

    def save_config(self, config):
        """Save configuration back to original source files."""
        scripts_path = self.get_config_value("paths.scripts_file", SCRIPTS_FILE)
        scripts_path = self.resolve_path(scripts_path)
        script_sources = config.get("_script_sources", {})
        if "scripts" in config and os.path.isdir(scripts_path):
            files_to_save = {}
            for script in config["scripts"]:
                script_name = script.get("name")
                source_file = script_sources.get(script_name)
                if source_file and os.path.exists(source_file):
                    if source_file not in files_to_save:
                        files_to_save[source_file] = []
                    files_to_save[source_file].append(script)
                else:
                    new_file = os.path.join(scripts_path, "_new.yaml")
                    if new_file not in files_to_save:
                        files_to_save[new_file] = []
                    files_to_save[new_file].append(script)
            for filepath, scripts in files_to_save.items():
                with open(filepath, "w") as f:
                    yaml.dump({"scripts": scripts}, f, default_flow_style=False, sort_keys=False)
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
    """Load configuration from scripts and groups directories."""
    return _default_config_manager.load_config(suppress_warnings=suppress_warnings)


def save_config(config):
    """Save configuration back to original source files."""
    return _default_config_manager.save_config(config)


def reset_config():
    """Reset the default configuration manager (useful for testing)."""
    _default_config_manager.reset()
