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
    """'09:00' today, 'Mon 12:00' within 6 days, 'Mon 23 Nov 12:00' further away."""
    if when.date() == now.date():
        return f"{when:%H:%M}"
    return f"{when:%a %H:%M}" if abs((when.date() - now.date()).days) < 7 else f"{when:%a %d %b %H:%M}"


def _group_row(group, state, last_run, now):
    """(status, detail, due) for one configured group; a scheduled group also says when it runs next.

    due is the missed due time of an overdue group, else None.
    """
    schedule = get_schedule_string(group) if "schedule" in group else ""
    upcoming = next_due_time(schedule, now) if schedule else None
    next_text = f", next {_clock(upcoming, now)}" if upcoming else ""
    if last_run is None:
        return "never", "never run" + next_text, None
    grace = OVERDUE_GRACE + timedelta(seconds=state.get("execution_time_seconds") or 0)
    due = last_due_time(schedule, now - grace) if schedule else None
    if due is not None and last_run < due:
        return "overdue", f"overdue: was due {_clock(due, now)}, last ran {ago(last_run, now)}{next_text}", due
    return state.get("last_status", "never"), ago(last_run, now) + next_text, None


def _latest_run_alerts(alerts, name, last_run):
    """The alerts that the task's latest run raised (an alert is recorded after its run started)."""
    if last_run is None:
        return []
    return [a for a in alerts if a.get("task_name") == name and (_when(a.get("timestamp")) or datetime.min) >= last_run]


def compute_status(config, runtime_state, ignore_failures_before=0, now=None, skip_warn_after=0, alerts=()):
    """Work out the icon colour, tooltip and menu rows.

    Red: a task or group failed, or a task's latest run raised a critical alert, or a
    config file does not load (its tasks and groups would otherwise just vanish).
    Yellow: nothing failed, but a scheduled group is overdue, a task's latest run raised a
    warning alert, or a task skipped skip_warn_after runs in a row (0 = never warn).
    Failures and alerts from runs before ignore_failures_before ("Mark all as seen") do not count.
    Green: everything else. A task or group that never ran, or that was skipped on
    purpose, is shown but does not count. Tasks for another platform are not shown.

    Returns:
        dict with:
          'colour', 'tooltip', and 'summary' (a short headline: "All OK", "1 failed, 2 warnings")
          'groups', 'tasks': rows of (icon, name, detail, status), sorted by name
          'group_tasks': {group name: its task rows}; 'other_tasks': rows of tasks in no group
          'attention': (colour, name, reason) for each item that makes the icon red or yellow
          'can_mark_seen': True if there are failures or warnings that "Mark all as seen" would hide
          'warnings': names of tasks whose latest run raised a warning alert not marked as seen
    """
    now = now or datetime.now()
    ignore_before = datetime.fromtimestamp(ignore_failures_before or 0)
    failed, overdue, skipping, warned, rows = [], [], [], [], {"groups": [], "tasks": []}
    attention = []

    for kind in ("groups", "tasks"):
        entries = [e for e in config.get(kind, []) if isinstance(e, dict) and isinstance(e.get("name"), str)]
        entries = [e for e in entries if on_this_platform(e)]
        for entry in sorted(entries, key=lambda e: e["name"]):
            name = entry["name"]
            state = runtime_state.get(kind, {}).get(name) or {}
            last_run = _when(state.get("last_run"))
            latest_alerts, due = [], None
            if kind == "groups":
                status, detail, due = _group_row(entry, state, last_run, now)
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
                    reason = f"skipped {skips} times in a row: {state.get('skip_reason') or 'no reason recorded'}"
                    attention.append(("yellow", name, reason))
            if kind == "tasks":
                latest_alerts = _latest_run_alerts(alerts, name, last_run)
                severities = [a.get("severity") for a in latest_alerts]
                if "critical" in severities and status == "success":
                    status = "alert"  # the command worked, but what it found is critical
                if severities:
                    counts = [f"{severities.count(s)} {s}" for s in ("critical", "warning", "info") if s in severities]
                    detail += f" ({', '.join(counts)} alert{'s' if len(severities) > 1 else ''})"
                if (
                    "warning" in severities
                    and "critical" not in severities
                    and status not in ("failed", "partial")  # a failure already makes it red
                    and last_run > ignore_before
                ):
                    warned.append(name)
                    attention.append(("yellow", name, _alert_message(latest_alerts, "warning")))
            if status in ("failed", "partial", "alert") and last_run and last_run > ignore_before:
                failed.append(name)
                reason = (
                    _alert_message(latest_alerts, "critical") if status == "alert" else f"{status} {ago(last_run, now)}"
                )
                attention.append(("red", name, reason))
            elif status == "overdue":
                overdue.append(name)
                attention.append(("yellow", name, f"overdue: was due {_clock(due, now)}"))
            rows[kind].append((ICONS.get(status, "?"), name, detail, status))

    # A config file that does not load hides its tasks and groups: never report that as green
    can_mark_seen = bool(failed or warned)
    load_errors = [os.path.basename(path) for path in config.get("_load_errors", {})]
    failed += [f"cannot load {name}" for name in load_errors]
    attention += [("red", name, "cannot load this file") for name in load_errors]
    if failed:
        colour = "red"
    elif overdue or skipping or warned:
        colour = "yellow"
    else:
        colour = "green"
    problems = [f"{len(failed)} failed: {', '.join(failed)}"] if failed else []
    problems += [f"{len(overdue)} overdue: {', '.join(overdue)}"] if overdue else []
    problems += [f"{len(skipping)} skipped repeatedly: {', '.join(skipping)}"] if skipping else []
    problems += [f"{len(warned)} with warnings: {', '.join(warned)}"] if warned else []
    anything_ran = any(row[3] != "never" for kind_rows in rows.values() for row in kind_rows)
    if problems:
        tooltip = "signalbox: " + "; ".join(problems)
    else:
        tooltip = "signalbox: all OK" if anything_ran else "signalbox: nothing has run yet"
    counts = [(len(failed), "failed"), (len(overdue), "late"), (len(skipping), "skipping"), (len(warned), "warning")]
    counts = [f"{n} {word}{'s' if word == 'warning' and n > 1 else ''}" for n, word in counts if n]
    summary = ", ".join(counts) or ("All OK" if anything_ran else "Nothing has run yet")
    attention.sort(key=lambda item: item[0] != "red")  # failures first; sort is stable
    task_rows = {row[1]: row for row in rows["tasks"]}
    group_tasks, grouped = {}, set()
    for entry in config.get("groups", []):
        if isinstance(entry, dict) and entry.get("name") in {row[1] for row in rows["groups"]}:
            members = [t for t in entry.get("tasks") or [] if isinstance(t, str) and t in task_rows]
            group_tasks[entry["name"]] = [task_rows[t] for t in members]
            grouped.update(members)
    return {
        "colour": colour,
        "tooltip": tooltip,
        "summary": summary,
        "attention": attention,
        "can_mark_seen": can_mark_seen,
        "warnings": warned,
        "group_tasks": group_tasks,
        "other_tasks": [row for row in rows["tasks"] if row[1] not in grouped],
        **rows,
    }


def _alert_message(alerts, severity):
    """The message of the first alert of this severity (what the task found), for the attention list."""
    return (
        next((str(a.get("message") or "") for a in alerts if a.get("severity") == severity), "") or f"{severity} alert"
    )


def read_status(now=None):
    """compute_status for the current config and runtime state (shared by the tray and `signalbox status`)."""
    config = load_config(suppress_warnings=True)
    runtime_state = filter_runtime_to_config(load_runtime_state(), config)
    tray_state = load_tray_state()
    # Fallback matches the value in the shipped signalbox.yaml
    skip_warn_after = get_config_value("execution.skip_warn_after", 3)
    alerts = load_alerts()
    result = compute_status(
        config, runtime_state, tray_state.get("ignore_failures_before", 0), now, skip_warn_after, alerts
    )
    # "Mark all as unseen" is useful only if the last "Mark all as seen" still hides something
    result["can_mark_unseen"] = "seen_previous" in tray_state and (
        compute_status(config, runtime_state, tray_state["seen_previous"], now, skip_warn_after, alerts)[
            "can_mark_seen"
        ]
    )
    return result
