# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

**Signalbox** is a Python CLI tool for managing, executing, and monitoring shell tasks with YAML-based configuration, detailed logging, group execution (serial/parallel), scheduling via systemd/cron export, pattern-based alerting, and an optional PyQt6 system tray GUI.

## Development Setup

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Optional: tray app support
pip install -e ".[dev,tray]"

# When developing, run as a module without installing globally
python -m signalbox list  # Uses ./config/ in current directory if present
```

## Common Commands

```bash
# Format code
./dev.sh format        # runs: black signalbox/
# or: black signalbox/ tests/

# Lint
./dev.sh lint          # runs: flake8 signalbox/
# or: flake8 signalbox/

# Run all checks (format + lint + tests)
./dev.sh check

# Run unit tests + CLI smoke test
bash test_all.sh

# Run unit tests only
pytest

# Run a single test file
pytest tests/test_executor.py

# Run a single test by name
pytest tests/test_executor.py::test_function_name -v
```

## Code Style

- **Formatter:** black, max line length **120** characters
- **Linter:** flake8 (configured in `.flake8`; flake8 does not read pyproject.toml)
- **Imports:** stdlib → third-party → local
- **Naming:** snake_case for variables/functions, UPPER_CASE for constants
- No type hints required; use clear variable names and docstrings
- Error output via `click.echo()`; raise exceptions from `signalbox/exceptions.py` and let the CLI layer's `@handle_exceptions` decorator translate them into messages and exit codes

## Architecture

### Entry Points

- `signalbox` console script → `signalbox/cli.py` (`cli` group); also runnable as `python -m signalbox`
- `signalbox-tray` console script → `signalbox/tray_app.py` (PyQt6 system tray app, requires the `[tray]` extra)

### CLI Layout

`signalbox/cli.py` defines the root Click group, registers command groups, and provides root shortcuts (`run`, `list`, `validate`). Commands live in `signalbox/commands/`:

| Module | Commands |
|--------|----------|
| `commands/task.py` | `task run`, `task list` |
| `commands/group.py` | `group run`, `group list` |
| `commands/log.py` | `log show/history/list/tail/clear` |
| `commands/config.py` | `config show/path/check-permissions/validate` |
| `commands/misc.py` | `init`, `list-schedules`, `export-systemd`, `export-cron`, `notify-test`, `alerts` |
| `commands/utils.py` | `handle_exceptions` decorator, output preview helper |

### Core Modules (`signalbox/`)

| Module | Responsibility |
|--------|----------------|
| `config.py` | `ConfigManager` class + module-level convenience functions; loads global config + all task/group YAML files from the config directory |
| `validator.py` | Validates YAML syntax, required fields, duplicates, per-task timeout, cron expressions |
| `executor.py` | Runs shell commands via `subprocess.run(shell=True)`, captures output, applies timeouts (per-task `timeout:` overrides `execution.default_timeout`) |
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

Config loads `signalbox.yaml` for global settings, then all `*.yaml`/`*.yml` files from `tasks/` and `groups/` subdirectories (hidden dotfiles are skipped). The `catalog/` subdirectory provides pre-built task/group templates. Code fallback defaults for `get_config_value` must stay identical to the values in the shipped `signalbox/config/signalbox.yaml`.

### Execution Flow

CLI command → `config.py` (load) → `validator.py` (validate) → `executor.py` (run via subprocess) → `log_manager.py` (write logs) → `alerts.py` (check patterns) → `runtime.py` (update state)

### Key Design Decisions

- Tasks run with `shell=True` to support pipes, redirection, and complex scripts
- Logs are write-once (never modified, only rotated/pruned)
- Runtime state is kept separate from config files
- No built-in scheduler daemon: scheduling is exported to systemd/cron
- PyQt6 is an optional extra (`[tray]`), not a hard dependency
- The tray app polls runtime state on a configurable interval (default 30s)
- Developer notes and planning scratch files live in `notes/` (not shipped)
