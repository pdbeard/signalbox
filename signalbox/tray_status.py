"""What the tray shows, worked out from config and runtime state (no Qt, so it can be tested).

The tray is a monitor: cron/systemd run the groups and the CLI records each run
in runtime/. A green icon must mean "ran and passed", not just "nothing failed",
so a scheduled group that missed its last due time counts as overdue.
"""

import os
from datetime import datetime, time, timedelta

from .exporters import get_schedule_string, is_cron_schedule
from .helpers import parse_timestamp

MACROS = {
    "@hourly": "0 * * * *",
    "@daily": "0 0 * * *",
    "@midnight": "0 0 * * *",
    "@weekly": "0 0 * * 0",
    "@monthly": "0 0 1 * *",
    "@yearly": "0 0 1 1 *",
    "@annually": "0 0 1 1 *",
}
DAY_NAMES = {name: i for i, name in enumerate(["sun", "mon", "tue", "wed", "thu", "fri", "sat"])}
MONTH_NAMES = {name: i + 1 for i, name in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}

# How late a scheduled group may be before it is overdue, on top of its last run time
OVERDUE_GRACE = timedelta(minutes=5)
# Longest gap to search back for a due time: a Feb 29 schedule fires once in 4 years
SEARCH_DAYS = 4 * 366

ICONS = {"success": "✓", "failed": "✗", "partial": "✗", "overdue": "⚠", "never": "–"}


def _cron_field(text, low, high, names=None):
    """The set of values one cron field allows, e.g. '*/15' -> {0, 15, 30, 45}."""

    def number(value):
        value = value.lower()
        return names[value[:3]] if names and value[:3] in names else int(value)

    values = set()
    for item in text.split(","):
        base, _, step = item.partition("/")
        step = int(step) if step else 1
        if base == "*":
            first, last = low, high
        elif "-" in base:
            first, last = (number(part) for part in base.split("-", 1))
        else:
            first = number(base)
            last = high if step > 1 else first  # "5/15" means from 5 to the end, every 15
        if not (low <= first <= last <= high) or step < 1:
            raise ValueError(f"cron field {text!r} out of range")
        values.update(range(first, last + 1, step))
    return values


def last_due_time(schedule, at):
    """The latest time at or before `at` when cron would start this schedule, or None.

    None also means "no expectation": @reboot, or syntax this parser does not know.
    """
    schedule = MACROS.get(schedule.strip(), schedule) if isinstance(schedule, str) else schedule
    if not is_cron_schedule(schedule) or schedule.startswith("@"):
        return None
    minute, hour, day, month, weekday = schedule.split()
    try:
        minutes = sorted(_cron_field(minute, 0, 59), reverse=True)
        hours = sorted(_cron_field(hour, 0, 23), reverse=True)
        days = _cron_field(day, 1, 31)
        months = _cron_field(month, 1, 12, MONTH_NAMES)
        weekdays = {d % 7 for d in _cron_field(weekday, 0, 7, DAY_NAMES)}  # 7 is Sunday too
    except ValueError:
        return None

    def day_matches(date):
        cron_weekday = (date.weekday() + 1) % 7  # Python: Monday=0; cron: Sunday=0
        # cron runs when EITHER day field matches, unless one starts with '*' (as in '*/2'): then BOTH must
        if not day.startswith("*") and not weekday.startswith("*"):
            return date.day in days or cron_weekday in weekdays
        return date.day in days and cron_weekday in weekdays

    at = at.replace(second=0, microsecond=0)
    for back in range(SEARCH_DAYS + 1):
        date = at.date() - timedelta(days=back)
        if date.month not in months or not day_matches(date):
            continue
        for h in hours:
            for m in minutes:
                due = datetime.combine(date, time(h, m))
                if due <= at:
                    return due
    return None


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
