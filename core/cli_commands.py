

# CLI command definitions for signalbox
import click
from datetime import datetime
import os
import shutil
import yaml

from .config import load_config, get_config_value, find_config_home
from .executor import run_script, run_group_parallel, run_group_serial

@click.group()
def cli():
	"""signalbox - Script execution control and monitoring."""
	pass

@cli.command()
def init():
	"""Initialize signalbox configuration in ~/.config/signalbox/"""
	config_dir = os.path.expanduser('~/.config/signalbox')
	
	if os.path.exists(config_dir):
		click.echo(f"Configuration directory already exists: {config_dir}")
		if not click.confirm("Do you want to reinitialize (this will backup existing config)?"):
			return
		# Backup existing config
		backup_dir = f"{config_dir}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
		shutil.move(config_dir, backup_dir)
		click.echo(f"Backed up existing config to: {backup_dir}")
	
	# Find the installed package's config templates
	# Try to locate the original config from the package installation
	try:
		import pkg_resources
		package_path = pkg_resources.resource_filename('signalbox', '')
		template_config = os.path.join(os.path.dirname(package_path), 'config')
		
		# If not found, try relative to this file (for development)
		if not os.path.exists(template_config):
			current_file_dir = os.path.dirname(os.path.abspath(__file__))
			template_config = os.path.join(os.path.dirname(current_file_dir), 'config')
	except:
		# Fallback to relative path from current module
		current_file_dir = os.path.dirname(os.path.abspath(__file__))
		template_config = os.path.join(os.path.dirname(current_file_dir), 'config')
	
	if os.path.exists(template_config):
		# Copy the entire config directory
		shutil.copytree(template_config, os.path.join(config_dir, 'config'))
		click.echo(f"✓ Created configuration directory: {config_dir}")
		click.echo(f"✓ Copied default config from: {template_config}")
	else:
		# Create minimal structure if template not found
		os.makedirs(config_dir, exist_ok=True)
		os.makedirs(os.path.join(config_dir, 'config/scripts'), exist_ok=True)
		os.makedirs(os.path.join(config_dir, 'config/groups'), exist_ok=True)
		
		# Create minimal signalbox.yaml
		default_config = {
			'default_log_limit': {'type': 'count', 'value': 10},
			'paths': {
				'log_dir': 'logs',
				'scripts_file': 'config/scripts',
				'groups_file': 'config/groups'
			},
			'execution': {
				'default_timeout': 300,
				'capture_stdout': True,
				'capture_stderr': True,
				'max_parallel_workers': 5
			},
			'logging': {'timestamp_format': '%Y%m%d_%H%M%S_%f'},
			'display': {'date_format': '%Y-%m-%d %H:%M:%S'}
		}
		
		with open(os.path.join(config_dir, 'config/signalbox.yaml'), 'w') as f:
			yaml.dump(default_config, f, default_flow_style=False, sort_keys=False)
		
		# Create example script
		example_script = {
			'scripts': [
				{
					'name': 'hello',
					'command': 'echo "Hello from signalbox!"',
					'description': 'Example script'
				}
			]
		}
		with open(os.path.join(config_dir, 'config/scripts/example.yaml'), 'w') as f:
			yaml.dump(example_script, f, default_flow_style=False, sort_keys=False)
		
		click.echo(f"✓ Created minimal configuration: {config_dir}")
	
	# Create logs and runtime directories
	os.makedirs(os.path.join(config_dir, 'logs'), exist_ok=True)
	os.makedirs(os.path.join(config_dir, 'runtime/scripts'), exist_ok=True)
	os.makedirs(os.path.join(config_dir, 'runtime/groups'), exist_ok=True)
	
	click.echo(f"✓ Created logs directory: {config_dir}/logs")
	click.echo(f"✓ Created runtime directory: {config_dir}/runtime")
	click.echo()
	click.echo("🎉 Signalbox initialized successfully!")
	click.echo()
	click.echo("Next steps:")
	click.echo(f"  1. Review configuration: {config_dir}/config/signalbox.yaml")
	click.echo(f"  2. Add your scripts: {config_dir}/config/scripts/")
	click.echo(f"  3. Run: signalbox list")
	click.echo()
	click.echo("You can now run signalbox from any directory!")

@cli.command()
def list():
	"""List all scripts and their status."""
	config = load_config()
	date_format = get_config_value('display.date_format', '%Y-%m-%d %H:%M:%S')
	for script in config['scripts']:
		status = script.get('last_status', 'not run')
		last_run = script.get('last_run', '')
		if last_run:
			try:
				timestamp_str = last_run.replace('.log', '')
				dt = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S_%f')
				human_date = dt.strftime(date_format)
				click.echo(f"{script['name']}: {status} ({human_date}) - {script['description']}")
			except ValueError:
				click.echo(f"{script['name']}: {status} ({last_run}) - {script['description']}")
		else:
			click.echo(f"{script['name']}: {status} - {script['description']}")

@cli.command()
@click.argument('name')
def run(name):
	"""Run a specific script by name."""
	config = load_config()
	run_script(name, config)

@cli.command()
def run_all():
	"""Run all scripts."""
	config = load_config()
	click.echo("Running all scripts...")
	for script in config['scripts']:
		click.echo(f"Running {script['name']}...")
		run_script(script['name'], config)
	click.echo("All scripts executed.")

@cli.command('run-group')
@click.argument('name')
def run_group(name):
	"""Run a group of scripts."""
	config = load_config()
	groups = config.get('groups', [])
	group = next((g for g in groups if g['name'] == name), None)
	if not group:
		click.echo(f"Group {name} not found")
		return
	execution_mode = group.get('execution', 'serial')
	stop_on_error = group.get('stop_on_error', False)
	click.echo(f"Running group {name}: {group['description']}")
	if execution_mode == 'parallel':
		click.echo(f"Execution mode: parallel")
	else:
		click.echo(f"Execution mode: serial (stop_on_error: {stop_on_error})")
	script_names = group['scripts']
	start_time = datetime.now()
	timestamp_format = get_config_value('logging.timestamp_format', '%Y%m%d_%H%M%S_%f')
	timestamp = start_time.strftime(timestamp_format)
	if execution_mode == 'parallel':
		scripts_successful = run_group_parallel(script_names, config)
	else:
		scripts_successful = run_group_serial(script_names, config, stop_on_error)
	end_time = datetime.now()
	execution_time = (end_time - start_time).total_seconds()
	scripts_total = len(script_names)
	if scripts_successful == scripts_total:
		group_status = 'success'
	elif scripts_successful > 0:
		group_status = 'partial'
	else:
		group_status = 'failed'
	# Saving group runtime state is handled in runtime.py
	click.echo(f"Group {name} executed.")
