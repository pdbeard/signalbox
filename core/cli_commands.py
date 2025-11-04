

# CLI command definitions for signalbox
import click
from datetime import datetime
import os

from .config import load_config, get_config_value
from .executor import run_script, run_group_parallel, run_group_serial

@click.group()
def cli():
	"""signalbox - Script execution control and monitoring."""
	pass

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
