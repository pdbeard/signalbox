# Agent Guide for signalbox

## Build/Test Commands
- **Run CLI**: `python signalbox.py <command>` (entry point wraps `core/cli_commands.py`)
- **Test all commands**: `./test_all.sh` (comprehensive test of all CLI commands)
- **Validate config**: `python signalbox.py validate`
- **No formal test suite**: No pytest/unittest currently - use manual testing via CLI

## Code Style Guidelines

### Structure
- Main entry: `signalbox.py` imports from `core/` module
- Core modules: `cli_commands.py`, `config.py`, `executor.py`, `runtime.py`, `notification.py`
- Config files: `config/signalbox.yaml` (settings), `config/scripts/*.yaml`, `config/groups/*.yaml`

### Imports
- Standard library first, third-party (click, yaml) second, local imports last
- Use relative imports for core modules: `from .config import load_config`

### Formatting
- Tabs for indentation (not spaces - check existing files)
- Simple, functional style - no complex OOP
- Click decorators for CLI commands: `@cli.command()`, `@click.argument('name')`

### Error Handling
- Use click.echo() for user messages (not print)
- Warnings to stderr: `click.echo(msg, err=True)`
- Graceful failures: return False/None on errors, don't crash

### Naming
- Functions: snake_case (`run_script`, `load_config`)
- Files: snake_case (`cli_commands.py`)
- YAML keys: snake_case (`default_timeout`, `stop_on_error`)

## Project Specific
- Python 3.8+ required
- Dependencies: click>=8.0.0, PyYAML>=5.4.0
- Configuration uses dot notation: `get_config_value('execution.default_timeout', 300)`
- All script/group definitions loaded from directories (not single files)
