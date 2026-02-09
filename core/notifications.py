"""
Cross-platform desktop notification system for Signalbox.

Supports macOS (via osascript) and Linux (via notify-send).
Falls back gracefully if notification systems are unavailable.
"""

import platform
import subprocess
import logging

logger = logging.getLogger(__name__)


def send_notification(title, message, urgency="normal"):
    """
    Send a desktop notification.

    Args:
        title: Notification title
        message: Notification message body
        urgency: Urgency level - "low", "normal", or "critical" (Linux only)

    Returns:
        bool: True if notification sent successfully, False otherwise
    """
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            return _send_macos_notification(title, message)
        elif system == "Linux":
            return _send_linux_notification(title, message, urgency)
        else:
            logger.warning(f"Notifications not supported on {system}")
            return False
    except Exception as e:
        logger.warning(f"Failed to send notification: {e}")
        return False


def _send_macos_notification(title, message):
    """Send notification on macOS using osascript."""
    # Escape quotes in title and message
    title = title.replace('"', '\\"')
    message = message.replace('"', '\\"')

    script = f'display notification "{message}" with title "{title}"'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)

    if result.returncode != 0:
        logger.warning(f"osascript failed: {result.stderr}")
        return False

    return True


def _send_linux_notification(title, message, urgency="normal"):
    """Send notification on Linux using notify-send."""
    # Check if notify-send is available
    result = subprocess.run(["which", "notify-send"], capture_output=True, text=True)

    if result.returncode != 0:
        logger.warning("notify-send not found. Install libnotify-bin or notification-daemon.")
        return False

    result = subprocess.run(["notify-send", "-u", urgency, title, message], capture_output=True, text=True, timeout=5)

    if result.returncode != 0:
        logger.warning(f"notify-send failed: {result.stderr}")
        return False

    return True


def format_summary(total, passed, failed, context="scripts", failed_names=None):
    """
    Format a summary message for script/group execution results.

    Args:
        total: Total number of scripts/groups executed
        passed: Number that passed
        failed: Number that failed
        context: "scripts" or "groups"
        failed_names: Optional list of failed script/group names

    Returns:
        str: Formatted message
    """
    if failed == 0:
        return f"All {context} ran successfully ({total}/{total})"

    message = f"Ran {total} {context}: {passed} passed, {failed} failed"

    # Include failed names if provided and count is reasonable
    if failed_names and len(failed_names) <= 3:
        names = ", ".join(failed_names)
        message += f"\nFailed: {names}"

    return message


def notify_execution_result(total, passed, failed, context="scripts", failed_names=None, config=None):
    """
    Send a notification summarizing execution results.

    Args:
        total: Total number executed
        passed: Number that passed
        failed: Number that failed
        context: "scripts" or "groups"
        failed_names: Optional list of failed names
        config: Config dict with notification settings

    Returns:
        bool: True if notification sent successfully
    """
    from .config import get_config_value
    
    # Get settings from global config (use new key group_notifications, fallback to old notifications key)
    enabled = get_config_value("group_notifications.enabled", 
                              get_config_value("notifications.enabled", True))
    on_failure_only = get_config_value("group_notifications.on_failure_only", 
                                       get_config_value("notifications.on_failure_only", True))
    show_failed_names = get_config_value("group_notifications.show_failed_names", 
                                         get_config_value("notifications.show_failed_names", True))

    # Check if we should send notification
    if not enabled:
        return False

    if on_failure_only and failed == 0:
        return False

    # Determine urgency and title
    if failed > 0:
        urgency = "critical"
        title = "Signalbox - Failures Detected"
    else:
        urgency = "normal"
        title = "Signalbox - Success"

    # Format message
    names_to_show = failed_names if show_failed_names else None
    message = format_summary(total, passed, failed, context, names_to_show)

    return send_notification(title, message, urgency)
