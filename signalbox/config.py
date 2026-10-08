# Configuration management for signalbox
import os
import yaml
from .helpers import load_yaml_files_from_dir

CONFIG_FILE = "config/signalbox.yaml"
# Fallback directories used when signalbox.yaml does not set paths.tasks_file /
# paths.groups_file. Kept identical to the values in the shipped signalbox.yaml.
TASKS_FILE = "config/tasks"
GROUPS_FILE = "config/groups"
CATALOG_TASKS_FILE = "config/catalog/tasks"
CATALOG_GROUPS_FILE = "config/catalog/groups"

# (config key, kind, fallback directory, is_catalog) for every place tasks/groups are loaded from
CONFIG_SOURCES = [
    ("paths.tasks_file", "tasks", TASKS_FILE, False),
    ("paths.catalog_tasks_file", "tasks", CATALOG_TASKS_FILE, True),
    ("paths.groups_file", "groups", GROUPS_FILE, False),
    ("paths.catalog_groups_file", "groups", CATALOG_GROUPS_FILE, True),
]


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
        self._explicit_home = config_home is not None
        self._global_config = None

    def find_init_home(self):
        """Find the directory that `signalbox init` should create or reinitialize.

        Same order as find_config_home but without the current-directory
        fallback: init replaces what it finds, so it must never pick an
        arbitrary project directory just because it contains config/signalbox.yaml.
        """
        if self._explicit_home:
            return self._config_home
        env_home = os.environ.get("SIGNALBOX_HOME")
        if env_home:
            return os.path.expanduser(env_home)
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            return os.path.expanduser(os.path.join(xdg_config_home, "signalbox"))
        return os.path.expanduser("~/.config/signalbox")

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

    def include_catalog(self):
        """Whether catalog tasks/groups are loaded. Off by default: catalog entries are examples."""
        return self.get_config_value("include_catalog", False)

    def config_sources(self):
        """Return (directory, kind, is_catalog) for each enabled task/group directory."""
        include_catalog = self.include_catalog()
        return [
            (self.resolve_path(self.get_config_value(key, fallback)), kind, is_catalog)
            for key, kind, fallback, is_catalog in CONFIG_SOURCES
            if include_catalog or not is_catalog
        ]

    def load_config(self, suppress_warnings=False):
        """Load configuration from tasks and groups directories."""
        config = {"tasks": [], "groups": [], "_task_sources": {}, "_group_sources": {}}
        sources_key = {"tasks": "_task_sources", "groups": "_group_sources"}

        for directory, kind, _ in self.config_sources():
            if not os.path.isdir(directory):
                continue
            items = load_yaml_files_from_dir(
                directory, key=kind, track_sources=True, suppress_warnings=suppress_warnings
            )
            for item in items:
                name = item["data"].get("name") if isinstance(item["data"], dict) else None
                if name:
                    config[sources_key[kind]][name] = item["source"]
                config[kind].append(item["data"])

        # Note: runtime state merging should be handled in runtime.py
        return config

    def _save_items(self, config, kind, directory_key, fallback):
        """Write config[kind] back to the files they were loaded from (new items go to _new.yaml)."""
        directory = self.resolve_path(self.get_config_value(directory_key, fallback))
        if kind not in config or not os.path.isdir(directory):
            return
        sources = config.get("_task_sources" if kind == "tasks" else "_group_sources", {})
        files_to_save = {}
        for item in config[kind]:
            source_file = sources.get(item.get("name"))
            if not (source_file and os.path.exists(source_file)):
                source_file = os.path.join(directory, "_new.yaml")
            files_to_save.setdefault(source_file, []).append(item)
        for filepath, items in files_to_save.items():
            with open(filepath, "w") as f:
                yaml.dump({kind: items}, f, default_flow_style=False, sort_keys=False)

    def save_config(self, config):
        """Save configuration back to original source files."""
        self._save_items(config, "tasks", "paths.tasks_file", TASKS_FILE)
        self._save_items(config, "groups", "paths.groups_file", GROUPS_FILE)

    def save_global_config_value(self, path, value):
        """Write a single value into signalbox.yaml using dot notation.

        Navigates or creates the nested key structure, writes the file
        atomically (temp file + rename), then invalidates the in-memory
        cache so the next read reflects the change.

        Args:
            path: Dot-notation key e.g. 'alerts.notifications.enabled'
            value: Value to set
        """
        import tempfile

        config_file = self.resolve_path(CONFIG_FILE)

        if os.path.exists(config_file):
            with open(config_file, "r") as f:
                config = yaml.safe_load(f) or {}
        else:
            config = {}

        keys = path.split(".")
        d = config
        for key in keys[:-1]:
            if key not in d or not isinstance(d[key], dict):
                d[key] = {}
            d = d[key]
        d[keys[-1]] = value

        config_dir = os.path.dirname(config_file)
        fd, tmp_path = tempfile.mkstemp(dir=config_dir, suffix=".yaml.tmp")
        try:
            with os.fdopen(fd, "w") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)
            os.replace(tmp_path, config_file)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        # Invalidate cache so next read picks up the new value
        self._global_config = None

    def set_config_home(self, config_home):
        """Set the config home directory explicitly and invalidate cached config.

        Public API used by the CLI --config option and the tray app; avoids
        callers reaching into private attributes.
        """
        self._config_home = config_home
        self._explicit_home = config_home is not None
        self._global_config = None

    def reset(self):
        """Reset cached configuration (useful for testing or reload)."""
        self._global_config = None
        self._config_home = None
        self._explicit_home = False


# Global instance for backward compatibility
# Modules can use this default instance or create their own
_default_config_manager = ConfigManager()


# Convenience functions that use the default instance
# These maintain backward compatibility with existing code
def find_config_home():
    """Find the signalbox configuration directory."""
    return _default_config_manager.find_config_home()


def find_init_home():
    """Find the directory `signalbox init` should create (never the current directory)."""
    return _default_config_manager.find_init_home()


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


def config_sources():
    """Return (directory, kind, is_catalog) for each enabled task/group directory."""
    return _default_config_manager.config_sources()


def save_config(config):
    """Save configuration back to original source files."""
    return _default_config_manager.save_config(config)


def set_config_home(config_home):
    """Set the config home directory on the default configuration manager."""
    _default_config_manager.set_config_home(config_home)


def save_global_config_value(path, value):
    """Write a single value into signalbox.yaml using dot notation."""
    _default_config_manager.save_global_config_value(path, value)


def reset_config():
    """Reset the default configuration manager (useful for testing)."""
    _default_config_manager.reset()
