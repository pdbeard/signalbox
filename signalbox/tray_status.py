"""What the tray shows, worked out from config and runtime state (no Qt, so it can be tested).

The tray is a monitor: cron/systemd run the groups and the CLI records each run
in runtime/. A green icon must mean "ran and passed", not just "nothing failed",
so a scheduled group that missed its last due time counts as overdue.
"""

import os
from datetime import datetime, timedelta

from .config import load_config
from .cron import last_due_time
from .exporters import get_schedule_string
from .helpers import parse_timestamp
from .runtime import filter_runtime_to_config, load_runtime_state, load_tray_state

# How late a scheduled group may be before it is overdue, on top of its last run time
OVERDUE_GRACE = timedelta(minutes=5)
ICONS = {"success": "✓", "failed": "✗", "partial": "✗", "overdue": "⚠", "never": "–"}


def _when(value):
    """A runtime last_run value as a datetime, or None."""
    if not value:
        return None
    parsed = parse_timestamp(str(value))
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    return parsed


def ago(then, now):
    """'5 min ago' style text for a datetime."""
    seconds = max(0, int((now - then).total_seconds()))
    for size, unit in ((86400, "d"), (3600, "h"), (60, "min")):
        if seconds >= size:
            return f"{seconds // size} {unit} ago"
    return f"{seconds} s ago"


def _group_row(group, state, last_run, now):
    """(status, detail) for one configured group."""
    schedule = get_schedule_string(group) if "schedule" in group else ""
    if last_run is None:
        return "never", "never run"
    grace = OVERDUE_GRACE + timedelta(seconds=state.get("execution_time_seconds") or 0)
    due = last_due_time(schedule, now - grace) if schedule else None
    if due is not None and last_run < due:
        due_text = f"{due:%H:%M}" if due.date() == now.date() else f"{due:%a %d %b %H:%M}"
        return "overdue", f"overdue: was due {due_text}, last ran {ago(last_run, now)} ({schedule})"
    return state.get("last_status", "never"), ago(last_run, now)


def compute_status(config, runtime_state, ignore_failures_before=0, now=None):
    """Work out the icon colour, tooltip and menu rows.

    Red: a task or group failed (and the user did not clear it with "Clear error state"),
    or a config file does not load (its tasks and groups would otherwise just vanish).
    Yellow: nothing failed, but a scheduled group is overdue.
    Green: everything else. A task or group that never ran is shown but does not count.

    Returns:
        dict with 'colour', 'tooltip', 'groups' and 'tasks'; each row is (icon, name, detail, status)
    """
    now = now or datetime.now()
    ignore_before = datetime.fromtimestamp(ignore_failures_before or 0)
    failed, overdue, rows = [], [], {"groups": [], "tasks": []}

    for kind in ("groups", "tasks"):
        entries = [e for e in config.get(kind, []) if isinstance(e, dict) and isinstance(e.get("name"), str)]
        for entry in sorted(entries, key=lambda e: e["name"]):
            name = entry["name"]
            state = runtime_state.get(kind, {}).get(name) or {}
            last_run = _when(state.get("last_run"))
            if kind == "groups":
                status, detail = _group_row(entry, state, last_run, now)
            elif last_run:
                status, detail = state.get("last_status", "never"), ago(last_run, now)
            else:
                status, detail = "never", "never run"
            if status in ("failed", "partial") and last_run and last_run > ignore_before:
                failed.append(name)
            elif status == "overdue":
                overdue.append(name)
            rows[kind].append((ICONS.get(status, "?"), name, detail, status))

    # A config file that does not load hides its tasks and groups: never report that as green
    failed += [f"cannot load {os.path.basename(path)}" for path in config.get("_load_errors", {})]
    if failed:
        colour = "red"
    elif overdue:
        colour = "yellow"
    else:
        colour = "green"
    problems = [f"{len(failed)} failed: {', '.join(failed)}"] if failed else []
    problems += [f"{len(overdue)} overdue: {', '.join(overdue)}"] if overdue else []
    if problems:
        tooltip = "signalbox: " + "; ".join(problems)
    elif any(row[3] != "never" for kind_rows in rows.values() for row in kind_rows):
        tooltip = "signalbox: all OK"
    else:
        tooltip = "signalbox: nothing has run yet"
    return {"colour": colour, "tooltip": tooltip, **rows}


def read_status(now=None):
    """compute_status for the current config and runtime state (shared by the tray and `signalbox status`)."""
    config = load_config(suppress_warnings=True)
    runtime_state = filter_runtime_to_config(load_runtime_state(), config)
    ignore_before = load_tray_state().get("ignore_failures_before", 0)
    return compute_status(config, runtime_state, ignore_before, now)
