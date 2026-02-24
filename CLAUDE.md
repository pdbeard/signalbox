# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

**Signalbox** is a Python CLI tool for managing, executing, and monitoring shell scripts with YAML-based configuration, detailed logging, group execution (serial/parallel), scheduling via systemd/cron export, pattern-based alerting, and a PyQt6 system tray GUI.

## Development Setup

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# When developing, run directly without installing globally
python signalbox.py list  # Uses ./config/ in current directory
```

## Common Commands

```bash
# Format code
./dev.sh format        # runs: black core/
# or: black core/

# Lint
./dev.sh lint          # runs: flake8 core/
# or: flake8 core/

# Run all checks (format + lint + tests)
./dev.sh check

# Run all tests
bash test_all.sh
# or: pytest

# Run a single test file
pytest tests/test_executor.py

# Run a single test by name
pytest tests/test_executor.py::test_function_name -v
```

## Code Style

- **Formatter:** black, max line length **120** characters
- **Linter:** flake8
- **Imports:** stdlib → third-party → local
- **Naming:** snake_case for variables/functions, UPPER_CASE for constants
- No type hints required; use clear variable names and docstrings
- Error output via `click.echo()`; fail gracefully with try/except

## Architecture

### Entry Points

- `signalbox.py` — delegates to `core/cli_commands.py`
- `core/cli_commands.py` — all CLI commands defined with Click decorators (~1000 lines)
- `core/tray_app.py` — PyQt6 system tray app (`signalbox-tray` command, ~900 lines)

### Core Modules

| Module | Responsibility |
|--------|----------------|
| `config.py` | Loads global config + all task/group YAML files from the config directory |
| `validator.py` | Validates YAML syntax, required fields, duplicates, cron expressions |
| `executor.py` | Runs shell commands via `subprocess.run(shell=True)`, captures output, applies timeouts |
| `log_manager.py` | Writes logs to `logs/<task>/<timestamp>.log`, handles rotation by count or age |
| `alerts.py` | Matches regex patterns against task output, appends to `logs/<task>/alerts/alerts.jsonl` |
| `notifications.py` | Sends desktop notifications on alert/failure |
| `runtime.py` | Reads/writes `runtime/tasks/` and `runtime/groups/` state files (last_run, last_status) |
| `exporters.py` | Generates systemd service/timer files and crontab entries for groups with `schedule` field |
| `cli_output*.py` | Rich-based terminal output formatting split across multiple files |

### Configuration Discovery Order

1. `$SIGNALBOX_HOME`
2. `$XDG_CONFIG_HOME/signalbox`
3. `~/.config/signalbox/`
4. `./config/` (current directory — used during development)

Config loads `signalbox.yaml` for global settings, then all `*.yaml`/`*.yml` files from `tasks/` and `groups/` subdirectories. The `catalog/` subdirectory provides pre-built task/group templates.

### Execution Flow

CLI command → `config.py` (load) → `validator.py` (validate) → `executor.py` (run via subprocess) → `log_manager.py` (write logs) → `alerts.py` (check patterns) → `runtime.py` (update state)

### Key Design Decisions

- Tasks run with `shell=True` to support pipes, redirection, and complex scripts
- Logs are write-once (never modified, only rotated/pruned)
- Runtime state is kept separate from config files
- The tray app polls runtime state on a configurable interval (default 30s)
