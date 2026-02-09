"""
Public API facade for signalbox.

This module provides a clean, stable programmatic interface for using signalbox
functionality from other Python code without going through the CLI.

Intended Purpose:
-----------------
- Expose key functions from internal modules (executor, validator, exporters, etc.)
- Provide simplified wrapper functions with sensible defaults
- Return structured result objects instead of printing to console
- Enable programmatic usage: `from signalbox import run_task, validate_config`
- Maintain API stability while allowing internal refactoring

Example Usage (when implemented):
----------------------------------
    from signalbox import run_task, run_group, validate_config

    # Run a single task programmatically
    result = run_task('backup_db', timeout=600)
    if result.success:
        print(f"Success: {result.output}")

    # Validate configuration
    validation = validate_config()
    if not validation.is_valid:
        print(f"Errors: {validation.errors}")

    # Export automation configs
    export_systemd('daily_backup', user=True)

TODO: Implement public API functions that wrap core modules
"""

# TODO: Add public API functions here
# Examples:
# - run_task(name, **kwargs) -> ExecutionResult
# - run_group(name, **kwargs) -> GroupExecutionResult
# - validate_config() -> ValidationResult
# - export_systemd(group_name, user=False) -> ExportResult
# - export_cron(group_name) -> ExportResult
