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


class TaskNotFoundError(SignalboxError):
    """Raised when a task is not found in configuration."""

    def __init__(self, task_name, hint=""):
        message = f"Task '{task_name}' not found.{hint}" if hint else f"Task '{task_name}' not found"
        super().__init__(message, exit_code=3)


class GroupNotFoundError(SignalboxError):
    """Raised when a group is not found in configuration."""

    def __init__(self, group_name, hint=""):
        message = f"Group '{group_name}' not found.{hint}" if hint else f"Group '{group_name}' not found"
        super().__init__(message, exit_code=3)


class ExecutionError(SignalboxError):
    """Raised when task execution fails."""

    def __init__(self, task_name, reason):
        message = f"Execution failed for '{task_name}': {reason}"
        super().__init__(message, exit_code=4)


class ExecutionTimeoutError(ExecutionError):
    """Raised when task execution times out."""

    def __init__(self, task_name, timeout):
        message = f"Task '{task_name}' timed out after {timeout} seconds"
        super().__init__(task_name, message)


class ValidationError(SignalboxError):
    """Raised when configuration validation fails."""

    def __init__(self, message):
        super().__init__(message, exit_code=2)


class TaskSkipped(SignalboxError):
    """A task did not run on purpose (run_if, overlap or platform). Not a failure: exit code 0."""

    def __init__(self, task_name, reason):
        self.task_name = task_name
        self.reason = reason
        super().__init__(f"Task '{task_name}' skipped: {reason}", exit_code=0)
