#!/usr/bin/env python3
"""
signalbox - Script execution control and monitoring
Control your scripts like a railway signal box controls trains
"""

import click
import yaml
import subprocess
import shutil
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPTS_FILE = 'scripts.yaml'
GROUPS_FILE = 'groups.yaml'
CONFIG_FILE = 'config.yaml'  # Global settings
LOG_DIR = 'logs'

# Global config cache
_global_config = None

def load_global_config():
    """Load global configuration settings from config.yaml."""
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
    """Load configuration from scripts file(s) and groups file."""
    config = {'scripts': [], 'groups': [], '_script_sources': {}}
    
    # Load scripts - supports both single file and directory
    scripts_path = get_config_value('paths.scripts_file', SCRIPTS_FILE)
    
    if os.path.isdir(scripts_path):
        # Load from directory - read all .yaml/.yml files
        for filename in sorted(os.listdir(scripts_path)):
            if filename.endswith(('.yaml', '.yml')) and not filename.startswith('.'):
                filepath = os.path.join(scripts_path, filename)
                try:
                    with open(filepath, 'r') as f:
                        scripts_data = yaml.safe_load(f)
                        if scripts_data and 'scripts' in scripts_data:
                            # Track which file each script came from
                            for script in scripts_data['scripts']:
                                script_name = script.get('name')
                                if script_name:
                                    config['_script_sources'][script_name] = filepath
                            config['scripts'].extend(scripts_data['scripts'])
                except Exception as e:
                    click.echo(f"Warning: Failed to load {filepath}: {e}", err=True)
    elif os.path.exists(scripts_path):
        # Load from single file (backwards compatible)
        with open(scripts_path, 'r') as f:
            scripts_data = yaml.safe_load(f)
            if scripts_data and 'scripts' in scripts_data:
                config['scripts'] = scripts_data['scripts']
                # Track single file source
                for script in config['scripts']:
                    script_name = script.get('name')
                    if script_name:
                        config['_script_sources'][script_name] = scripts_path
    
    # Load groups
    groups_file = get_config_value('paths.groups_file', GROUPS_FILE)
    if os.path.exists(groups_file):
        with open(groups_file, 'r') as f:
            groups_data = yaml.safe_load(f)
            if groups_data and 'groups' in groups_data:
                config['groups'] = groups_data['groups']
    
    return config

def save_config(config):
    """Save configuration back to original source files."""
    scripts_path = get_config_value('paths.scripts_file', SCRIPTS_FILE)
    script_sources = config.get('_script_sources', {})
    
    # Save scripts
    if 'scripts' in config:
        if os.path.isdir(scripts_path):
            # Save scripts back to their original files
            files_to_save = {}
            
            # Group scripts by source file
            for script in config['scripts']:
                script_name = script.get('name')
                source_file = script_sources.get(script_name)
                
                if source_file and os.path.exists(source_file):
                    if source_file not in files_to_save:
                        files_to_save[source_file] = []
                    files_to_save[source_file].append(script)
                else:
                    # New script or unknown source - save to _new.yaml
                    new_file = os.path.join(scripts_path, '_new.yaml')
                    if new_file not in files_to_save:
                        files_to_save[new_file] = []
                    files_to_save[new_file].append(script)
            
            # Write each file
            for filepath, scripts in files_to_save.items():
                with open(filepath, 'w') as f:
                    yaml.dump({'scripts': scripts}, f, default_flow_style=False, sort_keys=False)
        else:
            # Save to single file (backwards compatible)
            with open(scripts_path, 'w') as f:
                yaml.dump({'scripts': config['scripts']}, f, default_flow_style=False, sort_keys=False)
    
    # Save groups (if modified)
    if 'groups' in config:
        groups_file = get_config_value('paths.groups_file', GROUPS_FILE)
        # Only save if groups file exists (don't auto-create it)
        if os.path.exists(groups_file):
            with open(groups_file, 'r') as f:
                existing_groups = yaml.safe_load(f)
            # Only save if groups have changed (to avoid updating groups when running scripts)
            if existing_groups.get('groups') != config['groups']:
                with open(groups_file, 'w') as f:
                    yaml.dump({'groups': config['groups']}, f, default_flow_style=False, sort_keys=False)

def ensure_log_dir(script_name):
    log_dir = get_config_value('paths.log_dir', LOG_DIR)
    script_log_dir = os.path.join(log_dir, script_name)
    if not os.path.exists(script_log_dir):
        os.makedirs(script_log_dir)

def rotate_logs(script):
    name = script['name']
    log_dir = get_config_value('paths.log_dir', LOG_DIR)
    script_log_dir = os.path.join(log_dir, name)
    if not os.path.exists(script_log_dir):
        return  # No logs yet
    
    # Get default log limit from global config
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
    
    # Get timestamp format from global config
    timestamp_format = get_config_value('logging.timestamp_format', '%Y%m%d_%H%M%S_%f')
    timestamp = datetime.now().strftime(timestamp_format)
    
    log_dir = get_config_value('paths.log_dir', LOG_DIR)
    log_file = os.path.join(log_dir, name, f"{timestamp}.log")
    
    # Get timeout from global config
    timeout = get_config_value('execution.default_timeout', 300)
    if timeout == 0:
        timeout = None  # No timeout
    
    try:
        result = subprocess.run(
            script['command'], 
            shell=True, 
            capture_output=True, 
            text=True,
            timeout=timeout
        )
        
        # Write log based on global config settings
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
        # Update last status
        script['last_status'] = status
        script['last_run'] = timestamp
        save_config(config)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        click.echo(f"Script {name} timed out after {timeout} seconds")
        return False
    except Exception as e:
        click.echo(f"Error running {name}: {e}")
        return False

# CLI Commands

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
            # Convert timestamp to human-readable date
            # Format: 20251020_135925_405636 -> datetime object
            try:
                timestamp_str = last_run.replace('.log', '')
                dt = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S_%f')
                human_date = dt.strftime(date_format)
                click.echo(f"{script['name']}: {status} ({human_date}) - {script['description']}")
            except ValueError:
                # If parsing fails, show original format
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
    
    # Get execution mode from group config
    execution_mode = group.get('execution', 'serial')  # 'serial' or 'parallel'
    stop_on_error = group.get('stop_on_error', False)  # Only applies to serial execution
    
    click.echo(f"Running group {name}: {group['description']}")
    if execution_mode == 'parallel':
        click.echo(f"Execution mode: parallel")
    else:
        click.echo(f"Execution mode: serial (stop_on_error: {stop_on_error})")
    
    script_names = group['scripts']
    
    if execution_mode == 'parallel':
        # Parallel execution
        run_group_parallel(script_names, config)
    else:
        # Serial execution
        run_group_serial(script_names, config, stop_on_error)
    
    click.echo(f"Group {name} executed.")

def run_group_parallel(script_names, config):
    """Run scripts in parallel using thread pool."""
    max_workers = get_config_value('execution.max_parallel_workers', 5)
    
    def run_script_wrapper(script_name):
        """Wrapper to run script and return result."""
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

def run_group_serial(script_names, config, stop_on_error):
    """Run scripts serially, optionally stopping on first error."""
    for script_name in script_names:
        script = next((s for s in config['scripts'] if s['name'] == script_name), None)
        if script:
            click.echo(f"Running {script_name}...")
            success = run_script(script_name, config)
            
            if not success and stop_on_error:
                click.echo(f"⚠️  Script {script_name} failed. Stopping group execution (stop_on_error=true)")
                return
        else:
            click.echo(f"Script {script_name} not found in config")
            if stop_on_error:
                click.echo(f"⚠️  Script {script_name} not found. Stopping group execution (stop_on_error=true)")
                return

@cli.command()
@click.argument('name')
def logs(name):
    """Show the latest log for a script."""
    config = load_config()
    script = next((s for s in config['scripts'] if s['name'] == name), None)
    if not script:
        click.echo(f"Script {name} not found")
        return
    
    log_dir = get_config_value('paths.log_dir', 'logs')
    script_log_dir = os.path.join(log_dir, name)
    
    if not os.path.exists(script_log_dir):
        click.echo("No logs found")
        return
    # Show latest log
    log_files = os.listdir(script_log_dir)
    if not log_files:
        click.echo("No logs found")
        return
    
    latest = max(log_files, key=lambda x: os.path.getmtime(os.path.join(script_log_dir, x)))
    log_path = os.path.join(script_log_dir, latest)
    
    # Use display settings from global config
    include_paths = get_config_value('display.include_paths', False)
    show_colors = get_config_value('display.colors', True)
    
    if include_paths:
        click.echo(f"Log file: {log_path}")
        click.echo("=" * 50)
    
    with open(log_path, 'r') as f:
        content = f.read()
        if show_colors:
            # Add color to log content
            for line in content.split('\n'):
                if '[ERROR]' in line or ('exit_code:' in line and 'exit_code: 0' not in line):
                    click.echo(click.style(line, fg='red'))
                elif '[SUCCESS]' in line or 'exit_code: 0' in line:
                    click.echo(click.style(line, fg='green'))
                elif '[START]' in line:
                    click.echo(click.style(line, fg='blue'))
                else:
                    click.echo(line)
        else:
            click.echo(content)

@cli.command()
@click.argument('name')
def history(name):
    """Show all log files for a script."""
    config = load_config()
    script = next((s for s in config['scripts'] if s['name'] == name), None)
    if not script:
        click.echo(f"Script {name} not found")
        return
    
    log_dir = get_config_value('paths.log_dir', 'logs')
    script_log_dir = os.path.join(log_dir, name)
    
    if not os.path.exists(script_log_dir):
        click.echo("No history found")
        return
    log_files = os.listdir(script_log_dir)
    if not log_files:
        click.echo("No history found")
        return
    
    # Sort by time, newest first
    log_files.sort(key=lambda x: os.path.getmtime(os.path.join(script_log_dir, x)), reverse=True)
    
    # Use display settings from global config
    include_paths = get_config_value('display.include_paths', False)
    date_format = get_config_value('display.date_format', '%Y-%m-%d %H:%M:%S')
    
    path_info = f" ({script_log_dir})" if include_paths else ""
    click.echo(f"History for {name}{path_info}:")
    
    for f in log_files:
        mtime = os.path.getmtime(os.path.join(script_log_dir, f))
        time_str = datetime.fromtimestamp(mtime).strftime(date_format)
        click.echo(f"  {f} - {time_str}")

@cli.command()
@click.argument('name')
def clear_logs(name):
    """Clear all logs for a specific script."""
    config = load_config()
    script = next((s for s in config['scripts'] if s['name'] == name), None)
    if not script:
        click.echo(f"Script {name} not found")
        return
    
    log_dir = get_config_value('paths.log_dir', 'logs')
    script_log_dir = os.path.join(log_dir, name)
    
    if os.path.exists(script_log_dir):
        # Delete files but keep directory
        for f in os.listdir(script_log_dir):
            fpath = os.path.join(script_log_dir, f)
            if os.path.isfile(fpath):
                os.remove(fpath)
        click.echo(f"Cleared logs for {name}")
    else:
        click.echo(f"No logs found for {name}")

@cli.command()
def clear_all_logs():
    """Clear all logs for all scripts."""
    log_dir = get_config_value('paths.log_dir', 'logs')
    
    if os.path.exists(log_dir):
        # Recursively delete files but keep directories
        for root, dirs, files in os.walk(log_dir):
            for f in files:
                os.remove(os.path.join(root, f))
        click.echo("Cleared all logs")
    else:
        click.echo("No logs directory found")

@cli.command()
def list_groups():
    """List all available groups and their scripts."""
    config = load_config()
    groups = config.get('groups', [])
    if not groups:
        click.echo("No groups defined.")
        return
    for group in groups:
        schedule_info = f" [scheduled: {group['schedule']}]" if 'schedule' in group else ""
        execution_mode = group.get('execution', 'serial')
        stop_on_error = group.get('stop_on_error', False)
        
        # Build execution info
        exec_info = f" [execution: {execution_mode}"
        if execution_mode == 'serial' and stop_on_error:
            exec_info += ", stop_on_error"
        exec_info += "]"
        
        click.echo(f"Group: {group['name']} - {group.get('description', '')}{schedule_info}{exec_info}")
        click.echo("  Scripts:")
        for script_name in group.get('scripts', []):
            click.echo(f"    - {script_name}")
        click.echo("")

@cli.command()
def show_config():
    """Show global configuration settings."""
    global_config = load_global_config()
    
    if not global_config:
        click.echo("No global configuration found (config.yaml)")
        return
    
    click.echo("Global Configuration (config.yaml):\n")
    click.echo(yaml.dump(global_config, default_flow_style=False, sort_keys=False))

@cli.command()
@click.argument('key')
def get_setting(key):
    """Get a specific configuration value (use dot notation, e.g., 'execution.default_timeout')."""
    value = get_config_value(key)
    if value is None:
        click.echo(f"Setting '{key}' not found")
    else:
        click.echo(f"{key}: {value}")

@cli.command()
def list_schedules():
    """List all scheduled groups with their cron schedules."""
    config = load_config()
    groups = config.get('groups', [])
    scheduled = [g for g in groups if 'schedule' in g]
    
    if not scheduled:
        click.echo("No scheduled groups defined.")
        return
    
    click.echo("Scheduled Groups:")
    for group in scheduled:
        script_count = len(group.get('scripts', []))
        click.echo(f"\n  {group['name']}")
        click.echo(f"    Schedule: {group['schedule']}")
        click.echo(f"    Description: {group.get('description', 'N/A')}")
        click.echo(f"    Scripts: {script_count}")
        for script_name in group.get('scripts', []):
            click.echo(f"      - {script_name}")

@cli.command()
@click.argument('group_name')
@click.option('--user', is_flag=True, help='Generate for user systemd (not system-wide)')
def export_systemd(group_name, user):
    """Generate systemd service and timer files for a scheduled group."""
    config = load_config()
    groups = config.get('groups', [])
    group = next((g for g in groups if g['name'] == group_name), None)
    
    if not group:
        click.echo(f"Error: Group '{group_name}' not found")
        return
    
    if 'schedule' not in group:
        click.echo(f"Error: Group '{group_name}' has no schedule defined")
        click.echo("Add a 'schedule' field with a cron expression to the group in groups.yaml")
        return
    
    # Create export directory for this group (like logs)
    export_base_dir = get_config_value('paths.systemd_export_dir', 'systemd')
    export_dir = os.path.join(export_base_dir, group_name)
    os.makedirs(export_dir, exist_ok=True)
    
    # Get absolute path to script directory
    script_dir = os.path.abspath(os.path.dirname(__file__))
    python_exec = os.path.abspath(os.path.join(script_dir, 'venv', 'bin', 'python'))
    if not os.path.exists(python_exec):
        python_exec = 'python3'  # Fallback to system python
    
    service_name = f"signalbox-{group_name}"
    
    # Generate service file
    service_content = f"""[Unit]
Description=signalbox - {group['description']}
After=network.target

[Service]
Type=oneshot
WorkingDirectory={script_dir}
ExecStart={python_exec} {os.path.join(script_dir, 'main.py')} run-group {group_name}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    # Convert cron to systemd timer format
    cron_schedule = group['schedule']
    timer_content = f"""[Unit]
Description=Timer for signalbox - {group['description']}
Requires={service_name}.service

[Timer]
# Cron schedule: {cron_schedule}
OnCalendar=*-*-* *:00:00
# For custom timing, edit the OnCalendar line above
# Examples:
#   Every 5 minutes: *:0/5
#   Hourly: hourly
#   Daily at 2 AM: 02:00
#   See: man systemd.time

[Install]
WantedBy=timers.target
"""
    
    service_file = os.path.join(export_dir, f"{service_name}.service")
    timer_file = os.path.join(export_dir, f"{service_name}.timer")
    
    # Write files
    with open(service_file, 'w') as f:
        f.write(service_content)
    
    with open(timer_file, 'w') as f:
        f.write(timer_content)
    
    click.echo(f"✓ Generated {service_file}")
    click.echo(f"✓ Generated {timer_file}")
    click.echo(f"\nTo install (requires root):")
    
    if user:
        install_path = "~/.config/systemd/user/"
        click.echo(f"  mkdir -p {install_path}")
        click.echo(f"  cp {service_file} {timer_file} {install_path}")
        click.echo(f"  systemctl --user daemon-reload")
        click.echo(f"  systemctl --user enable {service_name}.timer")
        click.echo(f"  systemctl --user start {service_name}.timer")
        click.echo(f"\nTo check status:")
        click.echo(f"  systemctl --user status {service_name}.timer")
    else:
        click.echo(f"  sudo cp {service_file} {timer_file} /etc/systemd/system/")
        click.echo(f"  sudo systemctl daemon-reload")
        click.echo(f"  sudo systemctl enable {service_name}.timer")
        click.echo(f"  sudo systemctl start {service_name}.timer")
        click.echo(f"\nTo check status:")
        click.echo(f"  sudo systemctl status {service_name}.timer")

@cli.command()
@click.argument('group_name')
def export_cron(group_name):
    """Generate crontab entry for a scheduled group."""
    config = load_config()
    groups = config.get('groups', [])
    group = next((g for g in groups if g['name'] == group_name), None)
    
    if not group:
        click.echo(f"Error: Group '{group_name}' not found")
        return
    
    if 'schedule' not in group:
        click.echo(f"Error: Group '{group_name}' has no schedule defined")
        click.echo("Add a 'schedule' field with a cron expression to the group in groups.yaml")
        return
    
    # Create export directory for this group (like logs)
    export_base_dir = get_config_value('paths.cron_export_dir', 'cron')
    export_dir = os.path.join(export_base_dir, group_name)
    os.makedirs(export_dir, exist_ok=True)
    
    script_dir = os.path.abspath(os.path.dirname(__file__))
    python_exec = os.path.abspath(os.path.join(script_dir, 'venv', 'bin', 'python'))
    if not os.path.exists(python_exec):
        python_exec = 'python3'
    
    cron_line = f"{group['schedule']} cd {script_dir} && {python_exec} main.py run-group {group_name}"
    cron_file = os.path.join(export_dir, f"{group_name}.cron")
    
    # Write to file
    with open(cron_file, 'w') as f:
        f.write(f"# {group['description']}\n")
        f.write(f"{cron_line}\n")
    
    click.echo(f"✓ Generated {cron_file}")
    click.echo(f"\nCrontab entry:")
    click.echo(f"# {group['description']}")
    click.echo(cron_line)
    click.echo(f"\nTo install:")
    click.echo(f"  crontab -e")
    click.echo(f"Then add the line above to your crontab, or:")
    click.echo(f"  crontab -l > /tmp/mycron")
    click.echo(f"  cat {cron_file} >> /tmp/mycron")
    click.echo(f"  crontab /tmp/mycron")

@cli.command()
def validate():
    """Validate configuration files for errors."""
    try:
        # Check if files exist
        scripts_file = get_config_value('paths.scripts_file', SCRIPTS_FILE)
        groups_file = get_config_value('paths.groups_file', GROUPS_FILE)
        
        if not os.path.exists(scripts_file):
            click.echo(f"❌ Error: No scripts file found ({scripts_file})")
            return False
        
        config = load_config()
        errors = []
        warnings = []
        
        # Report which files are being used
        files_used = []
        if os.path.exists(CONFIG_FILE):
            files_used.append(f"{CONFIG_FILE} (global config)")
        if os.path.exists(scripts_file):
            files_used.append(scripts_file)
        if os.path.exists(groups_file):
            files_used.append(groups_file)
        
        click.echo(f"Validating: {', '.join(files_used)}\n")
        
        # Check scripts
        if 'scripts' not in config or not config['scripts']:
            errors.append("No scripts defined in config")
        else:
            script_names = [s['name'] for s in config['scripts']]
            
            # Check for duplicate script names
            if len(script_names) != len(set(script_names)):
                duplicates = [n for n in script_names if script_names.count(n) > 1]
                errors.append(f"Duplicate script names: {', '.join(set(duplicates))}")
            
            # Check required fields
            for script in config['scripts']:
                if 'name' not in script:
                    errors.append("Script missing 'name' field")
                if 'command' not in script:
                    errors.append(f"Script '{script.get('name', 'unknown')}' missing 'command' field")
            
            # Check for unused scripts (if enabled in global config)
            if get_config_value('validation.warn_unused_scripts', True):
                if 'groups' in config and config['groups']:
                    used_scripts = set()
                    for group in config['groups']:
                        used_scripts.update(group.get('scripts', []))
                    unused = set(script_names) - used_scripts
                    if unused:
                        warnings.append(f"Unused scripts (not in any group): {', '.join(unused)}")
        
        # Check groups
        if 'groups' in config:
            group_names = [g['name'] for g in config['groups']]
            
            # Check for duplicate group names
            if len(group_names) != len(set(group_names)):
                duplicates = [n for n in group_names if group_names.count(n) > 1]
                errors.append(f"Duplicate group names: {', '.join(set(duplicates))}")
            
            for group in config['groups']:
                if 'name' not in group:
                    errors.append("Group missing 'name' field")
                    continue
                
                group_name = group['name']
                
                # Check for empty groups (if enabled in global config)
                if get_config_value('validation.warn_empty_groups', True):
                    if 'scripts' not in group or not group['scripts']:
                        warnings.append(f"Group '{group_name}' has no scripts")
                else:
                    if 'scripts' in group and group['scripts']:
                        # Check if scripts exist
                        for script_name in group['scripts']:
                            if script_name not in script_names:
                                errors.append(f"Group '{group_name}' references non-existent script '{script_name}'")
                
                # Validate schedule if present
                if 'schedule' in group:
                    schedule = group['schedule']
                    parts = schedule.split()
                    if len(parts) != 5:
                        warnings.append(f"Group '{group_name}' schedule may be invalid: '{schedule}' (expected 5 fields)")
        
        # Check global config
        global_config = load_global_config()
        if global_config:
            # Validate timeout value
            timeout = get_config_value('execution.default_timeout', 300)
            if not isinstance(timeout, (int, float)) or timeout < 0:
                warnings.append(f"Invalid timeout value: {timeout} (should be >= 0)")
        
        # Print results
        strict_mode = get_config_value('validation.strict', False)
        
        if errors:
            click.echo("❌ Errors found:")
            for error in errors:
                click.echo(f"  - {error}")
        
        if warnings:
            click.echo("\n⚠️  Warnings:")
            for warning in warnings:
                click.echo(f"  - {warning}")
            if strict_mode:
                click.echo("\n❌ Validation failed (strict mode enabled)")
                return False
        
        if not errors and not warnings:
            click.echo("✓ Configuration is valid")
        elif not errors:
            click.echo("\n✓ No errors found (warnings only)")
            
        # Show summary
        if not errors or not warnings:
            script_count = len(config.get('scripts', []))
            group_count = len(config.get('groups', []))
            scheduled_count = len([g for g in config.get('groups', []) if 'schedule' in g])
            
            click.echo(f"\nSummary:")
            click.echo(f"  Scripts: {script_count}")
            click.echo(f"  Groups: {group_count}")
            click.echo(f"  Scheduled groups: {scheduled_count}")
            
            # Show global config summary
            if global_config:
                default_timeout = get_config_value('execution.default_timeout', 300)
                default_log_limit = get_config_value('default_log_limit', {})
                click.echo(f"  Default timeout: {default_timeout}s")
                click.echo(f"  Default log limit: {default_log_limit.get('type', 'count')} = {default_log_limit.get('value', 10)}")
        
        return len(errors) == 0 and (not strict_mode or len(warnings) == 0)
        
    except yaml.YAMLError as e:
        click.echo(f"❌ YAML syntax error: {e}")
        return False
    except Exception as e:
        click.echo(f"❌ Error loading config: {e}")
        return False

if __name__ == '__main__':
    cli()
