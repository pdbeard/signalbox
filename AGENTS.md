# AGENTS.md

## Build, Lint, and Test Commands
- Install for users: `pip install . --user`
- Install for development: `pip install -e ".[dev]"`
- Initialize config: `signalbox init`
- Run all tests: `bash test_all.sh`
- Run a single script: `signalbox run <script_name>`
- Run a group: `signalbox run-group <group_name>`
- Validate config: `signalbox validate`
- Lint (recommended): `flake8 .` or `black .`

## Code Style Guidelines
- **Imports:** Standard library first, then third-party, then local modules
- **Formatting:** Follow PEP8, prefer `black` formatting (4 spaces, max line length 88/120)
- **Types:** No type hints required, but use clear variable names and docstrings
- **Naming:** Use snake_case for variables/functions, UPPER_CASE for constants
- **Error Handling:** Use try/except, print errors with `click.echo`, fail gracefully
- **Configuration:** Use YAML for config, scripts, and groups; validate with CLI
- **Logging:** Store logs in `logs/`, rotate by count or age
- **CLI:** Expose commands via `click` decorators
- **Contributing:** Document new features, update validation logic, keep README up to date

## Agent/Copilot Rules
- Communicate concisely and systematically
- Work through checklist items methodically
- Follow development best practices
