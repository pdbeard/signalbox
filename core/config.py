# Configuration management for signalbox
import os
import yaml
import click

CONFIG_FILE = 'config/signalbox.yaml'
SCRIPTS_FILE = 'scripts.yaml'
GROUPS_FILE = 'groups.yaml'

_global_config = None

def load_global_config():
	"""Load global configuration settings from config/signalbox.yaml."""
	global _global_config
	if _global_config is None:
		if os.path.exists(CONFIG_FILE):
			with open(CONFIG_FILE, 'r') as f:
				_global_config = yaml.safe_load(f) or {}
		else:
			_global_config = {}
	return _global_config

def get_config_value(path, default=None):
	"""Get a configuration value using dot notation (e.g., 'execution.default_timeout')."""
	config = load_global_config()
	keys = path.split('.')
	value = config
	for key in keys:
		if isinstance(value, dict) and key in value:
			value = value[key]
		else:
			return default
	return value

def load_config():
	"""Load configuration from scripts and groups directories."""
	config = {'scripts': [], 'groups': [], '_script_sources': {}, '_group_sources': {}}
	# Load scripts from directory
	scripts_path = get_config_value('paths.scripts_file', SCRIPTS_FILE)
	if os.path.isdir(scripts_path):
		for filename in sorted(os.listdir(scripts_path)):
			if filename.endswith(('.yaml', '.yml')) and not filename.startswith('.'):
				filepath = os.path.join(scripts_path, filename)
				try:
					with open(filepath, 'r') as f:
						scripts_data = yaml.safe_load(f)
						if scripts_data and 'scripts' in scripts_data:
							for script in scripts_data['scripts']:
								script_name = script.get('name')
								if script_name:
									config['_script_sources'][script_name] = filepath
							config['scripts'].extend(scripts_data['scripts'])
				except Exception as e:
					click.echo(f"Warning: Failed to load {filepath}: {e}", err=True)
	# Load groups from directory
	groups_path = get_config_value('paths.groups_file', GROUPS_FILE)
	if os.path.isdir(groups_path):
		for filename in sorted(os.listdir(groups_path)):
			if filename.endswith(('.yaml', '.yml')) and not filename.startswith('.'):
				filepath = os.path.join(groups_path, filename)
				try:
					with open(filepath, 'r') as f:
						groups_data = yaml.safe_load(f)
						if groups_data and 'groups' in groups_data:
							for group in groups_data['groups']:
								group_name = group.get('name')
								if group_name:
									config['_group_sources'][group_name] = filepath
							config['groups'].extend(groups_data['groups'])
				except Exception as e:
					click.echo(f"Warning: Failed to load {filepath}: {e}", err=True)
	# Note: runtime state merging should be handled in runtime.py
	return config

def save_config(config):
	"""Save configuration back to original source files."""
	scripts_path = get_config_value('paths.scripts_file', SCRIPTS_FILE)
	script_sources = config.get('_script_sources', {})
	if 'scripts' in config and os.path.isdir(scripts_path):
		files_to_save = {}
		for script in config['scripts']:
			script_name = script.get('name')
			source_file = script_sources.get(script_name)
			if source_file and os.path.exists(source_file):
				if source_file not in files_to_save:
					files_to_save[source_file] = []
				files_to_save[source_file].append(script)
			else:
				new_file = os.path.join(scripts_path, '_new.yaml')
				if new_file not in files_to_save:
					files_to_save[new_file] = []
				files_to_save[new_file].append(script)
		for filepath, scripts in files_to_save.items():
			with open(filepath, 'w') as f:
				yaml.dump({'scripts': scripts}, f, default_flow_style=False, sort_keys=False)
	if 'groups' in config:
		groups_path = get_config_value('paths.groups_file', GROUPS_FILE)
		group_sources = config.get('_group_sources', {})
		if os.path.isdir(groups_path):
			files_to_save = {}
			for group in config['groups']:
				group_name = group.get('name')
				source_file = group_sources.get(group_name)
				if source_file and os.path.exists(source_file):
					if source_file not in files_to_save:
						files_to_save[source_file] = []
					files_to_save[source_file].append(group)
				else:
					new_file = os.path.join(groups_path, '_new.yaml')
					if new_file not in files_to_save:
						files_to_save[new_file] = []
					files_to_save[new_file].append(group)
			for filepath, groups in files_to_save.items():
				with open(filepath, 'w') as f:
					yaml.dump({'groups': groups}, f, default_flow_style=False, sort_keys=False)
