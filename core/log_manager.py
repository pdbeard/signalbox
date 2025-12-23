# Log management functionality for signalbox

import os
from datetime import datetime
from .config import get_config_value


def get_script_log_dir(script_name):
	"""Get the log directory path for a script."""
	log_dir = get_config_value('paths.log_dir', 'logs')
	return os.path.join(log_dir, script_name)


def get_latest_log(script_name):
	"""Get the path to the latest log file for a script.
	
	Returns:
		tuple: (log_path, log_exists) where log_path is the path to the latest log
		       and log_exists is True if logs were found
	"""
	script_log_dir = get_script_log_dir(script_name)
	
	if not os.path.exists(script_log_dir):
		return None, False
	
	log_files = os.listdir(script_log_dir)
	if not log_files:
		return None, False
	
	latest = max(log_files, key=lambda x: os.path.getmtime(os.path.join(script_log_dir, x)))
	return os.path.join(script_log_dir, latest), True


def read_log_content(log_path):
	"""Read the content of a log file."""
	with open(log_path, 'r') as f:
		return f.read()


def format_log_with_colors(content, show_colors=True):
	"""Format log content with color coding.
	
	Returns:
		list: List of tuples (line_text, color) where color can be 'red', 'green', 'blue', or None
	"""
	formatted_lines = []
	
	for line in content.split('\n'):
		color = None
		if show_colors:
			if '[ERROR]' in line or ('exit_code:' in line and 'exit_code: 0' not in line):
				color = 'red'
			elif '[SUCCESS]' in line or 'exit_code: 0' in line:
				color = 'green'
			elif '[START]' in line:
				color = 'blue'
		
		formatted_lines.append((line, color))
	
	return formatted_lines


def get_log_history(script_name):
	"""Get a list of all log files for a script with their timestamps.
	
	Returns:
		tuple: (log_files_info, history_exists) where log_files_info is a list of
		       tuples (filename, timestamp) sorted newest first
	"""
	script_log_dir = get_script_log_dir(script_name)
	
	if not os.path.exists(script_log_dir):
		return [], False
	
	log_files = os.listdir(script_log_dir)
	if not log_files:
		return [], False
	
	# Sort by time, newest first
	log_files.sort(key=lambda x: os.path.getmtime(os.path.join(script_log_dir, x)), reverse=True)
	
	log_info = []
	for filename in log_files:
		mtime = os.path.getmtime(os.path.join(script_log_dir, filename))
		log_info.append((filename, mtime))
	
	return log_info, True


def clear_script_logs(script_name):
	"""Clear all log files for a specific script.
	
	Returns:
		bool: True if logs were found and cleared, False otherwise
	"""
	script_log_dir = get_script_log_dir(script_name)
	
	if not os.path.exists(script_log_dir):
		return False
	
	# Delete files but keep directory
	for filename in os.listdir(script_log_dir):
		filepath = os.path.join(script_log_dir, filename)
		if os.path.isfile(filepath):
			os.remove(filepath)
	
	return True


def clear_all_logs():
	"""Clear all log files for all scripts.
	
	Returns:
		bool: True if log directory was found and cleared, False otherwise
	"""
	log_dir = get_config_value('paths.log_dir', 'logs')
	
	if not os.path.exists(log_dir):
		return False
	
	# Recursively delete files but keep directories
	for root, dirs, files in os.walk(log_dir):
		for filename in files:
			os.remove(os.path.join(root, filename))
	
	return True
