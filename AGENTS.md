# AGENTS.md

## Build, Lint, and Test Commands
- Install for users: `pip install . --user`
- Install for development: `pip install -e ".[dev]"`
- Initialize config: `signalbox init`
- Run all tests: `bash test_all.sh`
- Run a single task: `signalbox run <task_name>`
- Run a group: `signalbox group run <group_name>`
- Validate config: `signalbox validate`
- Lint/format: `./dev.sh lint` (flake8 signalbox/) and `./dev.sh format` (black signalbox/ tests/)

## Code Style Guidelines
- **Imports:** Standard library first, then third-party, then local modules
- **Formatting:** Follow PEP8, prefer `black` formatting (4 spaces, max line length 88/120)
- **Types:** No type hints required, but use clear variable names and docstrings
- **Naming:** Use snake_case for variables/functions, UPPER_CASE for constants
- **Error Handling:** The project uses a single convention: raise custom exceptions from `signalbox/exceptions.py` (`TaskNotFoundError`, `ExecutionError`, etc.) and let the CLI layer's `@handle_exceptions` decorator translate them into user-facing messages and exit codes. Do not use result objects (e.g. `return ExportResult(success=False)`) for error paths in core modules, and do not print-and-continue for failures that the caller needs to know about.
- **Configuration:** Use YAML for config, tasks, and groups; validate with CLI
- **Logging:** Store logs in `logs/`, rotate by count or age
- **CLI:** Expose commands via `click` decorators
- **Contributing:** Document new features, update validation logic, keep README up to date

## Agent/Copilot Rules
- Communicate concisely and systematically
- Work through checklist items methodically
- Follow development best practices
