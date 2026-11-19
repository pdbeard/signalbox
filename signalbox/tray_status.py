"""What the tray shows, worked out from config and runtime state (no Qt, so it can be tested).

The tray is a monitor: cron/systemd run the groups and the CLI records each run
in runtime/. A green icon must mean "ran and passed", not just "nothing failed",
so a scheduled group that missed its last due time counts as overdue.
"""

import os
from datetime import datetime, timedelta

from .alerts import load_alerts
from .config import load_config, get_config_value
from .cron import last_due_time, next_due_time
from .exporters import get_schedule_string
from .helpers import parse_timestamp, on_this_platform
from .runtime import filter_runtime_to_config, load_runtime_state, load_tray_state

# How late a scheduled group may be before it is overdue, on top of its last run time
OVERDUE_GRACE = timedelta(minutes=5)
ICONS = {"success": "✓", "failed": "✗", "partial": "✗", "alert": "✗", "overdue": "⚠", "never": "–", "skipped": "○"}


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
    """'5 min ago' style text for a datetime; a date ('on 2026-01-31') when it is a week or more ago."""
    seconds = max(0, int((now - then).total_seconds()))
    if seconds >= 7 * 86400:
        return f"on {then:%Y-%m-%d}"
    for size, unit in ((86400, "d"), (3600, "h"), (60, "min")):
        if seconds >= size:
            return f"{seconds // size} {unit} ago"
    return f"{seconds} s ago"


def _clock(when, now):
    """'09:00' today, 'Mon 23 Nov 12:00' on another day."""
    return f"{when:%H:%M}" if when.date() == now.date() else f"{when:%a %d %b %H:%M}"


def _group_row(group, state, last_run, now):
    """(status, detail) for one configured group; a scheduled group also says when it runs next."""
    schedule = get_schedule_string(group) if "schedule" in group else ""
    upcoming = next_due_time(schedule, now) if schedule else None
    next_text = f", next {_clock(upcoming, now)}" if upcoming else ""
    if last_run is None:
        return "never", "never run" + next_text
    grace = OVERDUE_GRACE + timedelta(seconds=state.get("execution_time_seconds") or 0)
    due = last_due_time(schedule, now - grace) if schedule else None
    if due is not None and last_run < due:
        return "overdue", f"overdue: was due {_clock(due, now)}, last ran {ago(last_run, now)}{next_text}"
    return state.get("last_status", "never"), ago(last_run, now) + next_text


def _latest_run_alerts(alerts, name, last_run):
    """The alerts that the task's latest run raised (an alert is recorded after its run started)."""
    if last_run is None:
        return []
    return [a for a in alerts if a.get("task_name") == name and (_when(a.get("timestamp")) or datetime.min) >= last_run]


def compute_status(config, runtime_state, ignore_failures_before=0, now=None, skip_warn_after=0, alerts=()):
    """Work out the icon colour, tooltip and menu rows.

    Red: a task or group failed, or a task's latest run raised a critical alert (and the
    user did not clear it with "Clear error state"), or a config file does not load (its
    tasks and groups would otherwise just vanish). A warning alert is shown and counted
    in 'warnings', but does not change the colour.
    Yellow: nothing failed, but a scheduled group is overdue, or a task skipped
    skip_warn_after runs in a row (0 = never warn).
    Green: everything else. A task or group that never ran, or that was skipped on
    purpose, is shown but does not count. Tasks for another platform are not shown.

    Returns:
        dict with 'colour', 'tooltip', 'groups', 'tasks' and 'warnings' (names of tasks whose
        latest run raised a warning alert); each row is (icon, name, detail, status)
    """
    now = now or datetime.now()
    ignore_before = datetime.fromtimestamp(ignore_failures_before or 0)
    failed, overdue, skipping, warned, rows = [], [], [], [], {"groups": [], "tasks": []}

    for kind in ("groups", "tasks"):
        entries = [e for e in config.get(kind, []) if isinstance(e, dict) and isinstance(e.get("name"), str)]
        entries = [e for e in entries if on_this_platform(e)]
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
            if status == "skipped" and kind == "tasks":
                skips = state.get("consecutive_skips") or 0
                detail = f"skipped: {state.get('skip_reason') or 'no reason recorded'}, {detail}"
                if skip_warn_after and isinstance(skips, int) and skips >= skip_warn_after:
                    skipping.append(name)
                    detail += f" ({skips} times in a row)"
            if kind == "tasks":
                severities = [a.get("severity") for a in _latest_run_alerts(alerts, name, last_run)]
                if "critical" in severities and status == "success":
                    status = "alert"  # the command worked, but what it found is critical
                if severities:
                    counts = [f"{severities.count(s)} {s}" for s in ("critical", "warning", "info") if s in severities]
                    detail += f" ({', '.join(counts)} alert{'s' if len(severities) > 1 else ''})"
                if "warning" in severities and "critical" not in severities:
                    warned.append(name)
            if status in ("failed", "partial", "alert") and last_run and last_run > ignore_before:
                failed.append(name)
            elif status == "overdue":
                overdue.append(name)
            rows[kind].append((ICONS.get(status, "?"), name, detail, status))

    # A config file that does not load hides its tasks and groups: never report that as green
    failed += [f"cannot load {os.path.basename(path)}" for path in config.get("_load_errors", {})]
    if failed:
        colour = "red"
    elif overdue or skipping:
        colour = "yellow"
    else:
        colour = "green"
    problems = [f"{len(failed)} failed: {', '.join(failed)}"] if failed else []
    problems += [f"{len(overdue)} overdue: {', '.join(overdue)}"] if overdue else []
    problems += [f"{len(skipping)} skipped repeatedly: {', '.join(skipping)}"] if skipping else []
    if problems:
        tooltip = "signalbox: " + "; ".join(problems)
    elif any(row[3] != "never" for kind_rows in rows.values() for row in kind_rows):
        tooltip = "signalbox: all OK"
    else:
        tooltip = "signalbox: nothing has run yet"
    if warned:
        tooltip += f" ({len(warned)} with warnings: {', '.join(warned)})"
    return {"colour": colour, "tooltip": tooltip, "warnings": warned, **rows}


def read_status(now=None):
    """compute_status for the current config and runtime state (shared by the tray and `signalbox status`)."""
    config = load_config(suppress_warnings=True)
    runtime_state = filter_runtime_to_config(load_runtime_state(), config)
    ignore_before = load_tray_state().get("ignore_failures_before", 0)
    # Fallback matches the value in the shipped signalbox.yaml
    skip_warn_after = get_config_value("execution.skip_warn_after", 3)
    return compute_status(config, runtime_state, ignore_before, now, skip_warn_after, load_alerts())
