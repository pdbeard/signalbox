# Script and group execution logic for signalbox
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import click

from .config import get_config_value
from .runtime import save_script_runtime_state
from .logger import ensure_log_dir, get_log_path, write_execution_log
from .log_rotation import rotate_logs


def run_script(name, config):
	"""Execute a single script and log the results.
	
	Args:
		name: Name of the script to run
		config: Full configuration dict containing scripts
	
	Returns:
		bool: True if script executed successfully (exit code 0), False otherwise
	"""
	script = next((s for s in config['scripts'] if s['name'] == name), None)
	if not script:
		click.echo(f"Script {name} not found")
		return False
	
	# Prepare logging
	ensure_log_dir(name)
	timestamp_format = get_config_value('logging.timestamp_format', '%Y%m%d_%H%M%S_%f')
	timestamp = datetime.now().strftime(timestamp_format)
	log_file = get_log_path(name, timestamp)
	
	# Get timeout setting
	timeout = get_config_value('execution.default_timeout', 300)
	if timeout == 0:
		timeout = None
	
	try:
		# Execute the script
		result = subprocess.run(
			script['command'],
			shell=True,
			capture_output=True,
			text=True,
			timeout=timeout
		)
		
		# Write log file
		write_execution_log(
			log_file,
			script['command'],
			result.returncode,
			result.stdout,
			result.stderr
		)
		
		# Rotate old logs
		rotate_logs(script)
		
		# Determine status and save runtime state
		status = 'success' if result.returncode == 0 else 'failed'
		click.echo(f"Script {name} {status}. Log: {log_file}")
		
		script_source_file = config['_script_sources'].get(name)
		if script_source_file:
			save_script_runtime_state(name, script_source_file, timestamp, status)
		
		# Update in-memory config
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
	"""Execute multiple scripts in parallel.
	
	Args:
		script_names: List of script names to execute
		config: Full configuration dict
	
	Returns:
		int: Number of scripts that executed successfully
	"""
	max_workers = get_config_value('execution.max_parallel_workers', 5)
	
	def run_script_wrapper(script_name):
		"""Wrapper for parallel execution."""
		script = next((s for s in config['scripts'] if s['name'] == script_name), None)
		if script:
			click.echo(f"Running {script_name}...")
			success = run_script(script_name, config)
			return (script_name, success)
		else:
			click.echo(f"Script {script_name} not found in config")
			return (script_name, False)
	
	# Execute scripts in parallel
	with ThreadPoolExecutor(max_workers=max_workers) as executor:
		futures = {executor.submit(run_script_wrapper, name): name for name in script_names}
		results = []
		for future in as_completed(futures):
			script_name, success = future.result()
			results.append((script_name, success))
	
	# Print summary
	click.echo("\nParallel execution summary:")
	success_count = sum(1 for _, success in results if success)
	click.echo(f"  Completed: {len(results)}/{len(script_names)}")
	click.echo(f"  Successful: {success_count}/{len(results)}")
	
	if success_count < len(results):
		failed = [name for name, success in results if not success]
		click.echo(f"  Failed: {', '.join(failed)}")
	
	return success_count


def run_group_serial(script_names, config, stop_on_error):
	"""Execute multiple scripts sequentially.
	
	Args:
		script_names: List of script names to execute
		config: Full configuration dict
		stop_on_error: If True, stop execution when a script fails
	
	Returns:
		int: Number of scripts that executed successfully
	"""
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
