# Custom exceptions for signalbox
"""
Centralized exception handling for signalbox.

This module defines custom exceptions to provide consistent error handling
across the application. All exceptions inherit from SignalboxError.
"""


class SignalboxError(Exception):
    """Base exception for all signalbox errors."""

    def __init__(self, message, exit_code=1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(self.message)


class ConfigurationError(SignalboxError):
    """Raised when configuration is invalid or cannot be loaded."""

    def __init__(self, message):
        super().__init__(message, exit_code=2)




class ScriptNotFoundError(SignalboxError):
    """Raised when a script is not found in configuration."""

    def __init__(self, script_name):
        message = f"Script '{script_name}' not found"
        super().__init__(message, exit_code=3)

class TaskNotFoundError(SignalboxError):
    """Raised when a task is not found in configuration."""

    def __init__(self, task_name):
        message = f"Task '{task_name}' not found"
        super().__init__(message, exit_code=3)


class GroupNotFoundError(SignalboxError):
    """Raised when a group is not found in configuration."""

    def __init__(self, group_name):
        message = f"Group '{group_name}' not found"
        super().__init__(message, exit_code=3)


class ExecutionError(SignalboxError):
    """Raised when script execution fails."""

    def __init__(self, script_name, reason):
        message = f"Execution failed for '{script_name}': {reason}"
        super().__init__(message, exit_code=4)


class ExecutionTimeoutError(ExecutionError):
    """Raised when script execution times out."""

    def __init__(self, script_name, timeout):
        message = f"Script '{script_name}' timed out after {timeout} seconds"
        super().__init__(script_name, message)


class ValidationError(SignalboxError):
    """Raised when configuration validation fails."""

    def __init__(self, message):
        super().__init__(message, exit_code=5)


class ExportError(SignalboxError):
    """Raised when export operation fails."""

    def __init__(self, message):
        super().__init__(message, exit_code=6)


class LogError(SignalboxError):
    """Raised when log operations fail."""

    def __init__(self, message):
        super().__init__(message, exit_code=7)
