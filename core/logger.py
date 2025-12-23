# Logging functionality for signalbox

import os
from datetime import datetime
from .config import get_config_value


def ensure_log_dir(script_name):
	"""Ensure the log directory exists for a script."""
	log_dir = get_config_value('paths.log_dir', 'logs')
	script_log_dir = os.path.join(log_dir, script_name)
	if not os.path.exists(script_log_dir):
		os.makedirs(script_log_dir)


def get_log_path(script_name, timestamp=None):
	"""Get the full path for a log file.
	
	Args:
		script_name: Name of the script
		timestamp: Optional timestamp string, defaults to current time
	
	Returns:
		str: Full path to the log file
	"""
	if timestamp is None:
		timestamp_format = get_config_value('logging.timestamp_format', '%Y%m%d_%H%M%S_%f')
		timestamp = datetime.now().strftime(timestamp_format)
	
	log_dir = get_config_value('paths.log_dir', 'logs')
	return os.path.join(log_dir, script_name, f"{timestamp}.log")


def write_execution_log(log_file, command, return_code, stdout, stderr):
	"""Write execution results to a log file.
	
	Args:
		log_file: Path to the log file
		command: The command that was executed
		return_code: Exit code from the command
		stdout: Standard output from the command
		stderr: Standard error from the command
	"""
	with open(log_file, 'w') as f:
		if get_config_value('logging.include_command', True):
			f.write(f"Command: {command}\n")
		
		if get_config_value('logging.include_return_code', True):
			f.write(f"Return code: {return_code}\n")
		
		if get_config_value('execution.capture_stdout', True):
			f.write("STDOUT:\n" + stdout + "\n")
		
		if get_config_value('execution.capture_stderr', True):
			f.write("STDERR:\n" + stderr + "\n")
