# Log rotation functionality for signalbox

import os
from datetime import datetime, timedelta
from .config import get_config_value


def rotate_logs(script):
	"""Rotate logs for a script based on configured limits.
	
	Supports two rotation types:
	- 'count': Keep only the N most recent log files
	- 'age': Delete log files older than N days
	
	Args:
		script: Script configuration dict with optional 'log_limit' setting
	"""
	name = script['name']
	log_dir = get_config_value('paths.log_dir', 'logs')
	script_log_dir = os.path.join(log_dir, name)
	
	if not os.path.exists(script_log_dir):
		return
	
	# Get log limit settings
	default_limit = get_config_value('default_log_limit', {'type': 'count', 'value': 10})
	log_limit = script.get('log_limit', default_limit)
	
	log_files = os.listdir(script_log_dir)
	
	if log_limit['type'] == 'count':
		_rotate_by_count(script_log_dir, log_files, log_limit['value'])
	elif log_limit['type'] == 'age':
		_rotate_by_age(script_log_dir, log_files, log_limit['value'])


def _rotate_by_count(script_log_dir, log_files, max_count):
	"""Keep only the most recent N log files.
	
	Args:
		script_log_dir: Directory containing log files
		log_files: List of log filenames
		max_count: Maximum number of log files to keep
	"""
	if len(log_files) <= max_count:
		return
	
	# Sort by modification time (oldest first)
	log_files.sort(key=lambda x: os.path.getmtime(os.path.join(script_log_dir, x)))
	
	# Delete oldest files to keep only max_count
	to_delete = log_files[:-max_count]
	for filename in to_delete:
		os.remove(os.path.join(script_log_dir, filename))


def _rotate_by_age(script_log_dir, log_files, max_age_days):
	"""Delete log files older than N days.
	
	Args:
		script_log_dir: Directory containing log files
		log_files: List of log filenames
		max_age_days: Maximum age of log files in days
	"""
	cutoff = datetime.now() - timedelta(days=max_age_days)
	
	for filename in log_files:
		filepath = os.path.join(script_log_dir, filename)
		file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
		
		if file_time < cutoff:
			os.remove(filepath)
