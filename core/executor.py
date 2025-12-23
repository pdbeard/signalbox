# Script and group execution logic for signalbox
import os
import subprocess
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import click

from .config import get_config_value, resolve_path
from .runtime import save_script_runtime_state, save_group_runtime_state

def ensure_log_dir(script_name):
	log_dir = get_config_value('paths.log_dir', 'logs')
	log_dir = resolve_path(log_dir)
	script_log_dir = os.path.join(log_dir, script_name)
	if not os.path.exists(script_log_dir):
		os.makedirs(script_log_dir)

def rotate_logs(script):
	name = script['name']
	log_dir = get_config_value('paths.log_dir', 'logs')
	log_dir = resolve_path(log_dir)
	script_log_dir = os.path.join(log_dir, name)
	if not os.path.exists(script_log_dir):
		return
	default_limit = get_config_value('default_log_limit', {'type': 'count', 'value': 10})
	log_limit = script.get('log_limit', default_limit)
	log_files = os.listdir(script_log_dir)
	if log_limit['type'] == 'count':
		if len(log_files) > log_limit['value']:
			log_files.sort(key=lambda x: os.path.getmtime(os.path.join(script_log_dir, x)))
			to_delete = log_files[:-log_limit['value']]
			for f in to_delete:
				os.remove(os.path.join(script_log_dir, f))
	elif log_limit['type'] == 'age':
		cutoff = datetime.now() - timedelta(days=log_limit['value'])
		for f in log_files:
			fpath = os.path.join(script_log_dir, f)
			if datetime.fromtimestamp(os.path.getmtime(fpath)) < cutoff:
				os.remove(fpath)

def run_script(name, config):
	script = next((s for s in config['scripts'] if s['name'] == name), None)
	if not script:
		click.echo(f"Script {name} not found")
		return False
	ensure_log_dir(name)
	timestamp_format = get_config_value('logging.timestamp_format', '%Y%m%d_%H%M%S_%f')
	timestamp = datetime.now().strftime(timestamp_format)
	log_dir = get_config_value('paths.log_dir', 'logs')
	log_dir = resolve_path(log_dir)
	log_file = os.path.join(log_dir, name, f"{timestamp}.log")
	timeout = get_config_value('execution.default_timeout', 300)
	if timeout == 0:
		timeout = None
	try:
		result = subprocess.run(
			script['command'],
			shell=True,
			capture_output=True,
			text=True,
			timeout=timeout
		)
		with open(log_file, 'w') as f:
			if get_config_value('logging.include_command', True):
				f.write(f"Command: {script['command']}\n")
			if get_config_value('logging.include_return_code', True):
				f.write(f"Return code: {result.returncode}\n")
			if get_config_value('execution.capture_stdout', True):
				f.write("STDOUT:\n" + result.stdout + "\n")
			if get_config_value('execution.capture_stderr', True):
				f.write("STDERR:\n" + result.stderr + "\n")
		rotate_logs(script)
		status = 'success' if result.returncode == 0 else 'failed'
		click.echo(f"Script {name} {status}. Log: {log_file}")
		script_source_file = config['_script_sources'].get(name)
		if script_source_file:
			save_script_runtime_state(name, script_source_file, timestamp, status)
		script['last_status'] = status
		script['last_run'] = timestamp
		return result.returncode == 0
	except subprocess.TimeoutExpired:
		click.echo(f"Script {name} timed out after {timeout} seconds")
		return False
	except Exception as e:
		click.echo(f"Error running {name}: {e}")
		return False

def run_group_parallel(script_names, config):
	max_workers = get_config_value('execution.max_parallel_workers', 5)
	def run_script_wrapper(script_name):
		script = next((s for s in config['scripts'] if s['name'] == script_name), None)
		if script:
			click.echo(f"Running {script_name}...")
			success = run_script(script_name, config)
			return (script_name, success)
		else:
			click.echo(f"Script {script_name} not found in config")
			return (script_name, False)
	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		futures = {executor.submit(run_script_wrapper, name): name for name in script_names}
		results = []
		for future in as_completed(futures):
			script_name, success = future.result()
			results.append((script_name, success))
	click.echo("\nParallel execution summary:")
	success_count = sum(1 for _, success in results if success)
	click.echo(f"  Completed: {len(results)}/{len(script_names)}")
	click.echo(f"  Successful: {success_count}/{len(results)}")
	if success_count < len(results):
		failed = [name for name, success in results if not success]
		click.echo(f"  Failed: {', '.join(failed)}")
	return success_count

def run_group_serial(script_names, config, stop_on_error):
	success_count = 0
	for script_name in script_names:
		script = next((s for s in config['scripts'] if s['name'] == script_name), None)
		if script:
			click.echo(f"Running {script_name}...")
			success = run_script(script_name, config)
			if success:
				success_count += 1
			elif stop_on_error:
				click.echo(f"⚠️  Script {script_name} failed. Stopping group execution (stop_on_error=true)")
				return success_count
		else:
			click.echo(f"Script {script_name} not found in config")
			if stop_on_error:
				click.echo(f"⚠️  Script {script_name} not found. Stopping group execution (stop_on_error=true)")
				return success_count
	return success_count
