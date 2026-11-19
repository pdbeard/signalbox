"""Cron schedules: the one parser behind `signalbox validate`, the exporters and the tray.

All three must agree on what a valid schedule is: a schedule that validates but
that cron rejects would never run, and the tray could not tell that it is late.
"""

from datetime import datetime, time, timedelta

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
# (name, lowest, highest, names) for the 5 fields in order; day-of-week 7 is Sunday too
FIELDS = (
    ("minute", 0, 59, None),
    ("hour", 0, 23, None),
    ("day-of-month", 1, 31, None),
    ("month", 1, 12, MONTH_NAMES),
    ("day-of-week", 0, 7, DAY_NAMES),
)

# Longest gap to search back for a due time: a Feb 29 schedule fires once in 4 years
SEARCH_DAYS = 4 * 366


def _field_values(text, low, high, names=None):
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
            raise ValueError("out of range")
        values.update(range(first, last + 1, step))
    return values


def parse(schedule):
    """The allowed values of each field of a 5-field schedule (macros expanded).

    Returns:
        list of 5 sets, in FIELDS order (day-of-week uses 0-6, Sunday = 0)

    Raises:
        ValueError: with a message that names the bad field
    """
    schedule = MACROS.get(schedule.strip(), schedule)
    fields = schedule.split()
    if len(fields) != 5:
        raise ValueError(f"expected 5 cron fields or an @macro, got {schedule!r}")
    values = []
    for text, (name, low, high, names) in zip(fields, FIELDS):
        try:
            values.append(_field_values(text, low, high, names))
        except ValueError:
            raise ValueError(f"invalid {name} field {text!r} (allowed: {low}-{high})") from None
    values[4] = {d % 7 for d in values[4]}
    return values


def schedule_error(schedule):
    """Why cron would reject this schedule, or None if it is valid (@reboot included)."""
    if not isinstance(schedule, str):
        return f"schedule must be text, got {schedule!r}"
    if schedule.strip() == "@reboot":
        return None
    if schedule.strip().startswith("@") and schedule.strip() not in MACROS:
        return f"unknown macro {schedule.strip()!r} (use {', '.join(sorted(MACROS))} or @reboot)"
    try:
        parse(schedule)
    except ValueError as e:
        return str(e)
    return None


def _matcher(schedule):
    """(minutes, hours, day_matches(date)) for a schedule, or None for @reboot or an invalid schedule."""
    if schedule_error(schedule) or schedule.strip() == "@reboot":
        return None
    minutes, hours, days, months, weekdays = parse(schedule)
    day, weekday = MACROS.get(schedule.strip(), schedule).split()[2::2]

    def day_matches(date):
        if date.month not in months:
            return False
        cron_weekday = (date.weekday() + 1) % 7  # Python: Monday=0; cron: Sunday=0
        # cron runs when EITHER day field matches, unless one starts with '*' (as in '*/2'): then BOTH must
        if not day.startswith("*") and not weekday.startswith("*"):
            return date.day in days or cron_weekday in weekdays
        return date.day in days and cron_weekday in weekdays

    return minutes, hours, day_matches


def last_due_time(schedule, at):
    """The latest time at or before `at` when cron would start this schedule, or None.

    None also means "no expectation": @reboot, or a schedule that schedule_error rejects.
    """
    matcher = _matcher(schedule)
    if matcher is None:
        return None
    minutes, hours, day_matches = matcher
    minutes, hours = sorted(minutes, reverse=True), sorted(hours, reverse=True)

    at = at.replace(second=0, microsecond=0)
    for back in range(SEARCH_DAYS + 1):
        date = at.date() - timedelta(days=back)
        if not day_matches(date):
            continue
        for h in hours:
            for m in minutes:
                due = datetime.combine(date, time(h, m))
                if due <= at:
                    return due
    return None


def next_due_time(schedule, after):
    """The first time after `after` when cron would start this schedule, or None (@reboot, invalid)."""
    matcher = _matcher(schedule)
    if matcher is None:
        return None
    minutes, hours, day_matches = matcher
    minutes, hours = sorted(minutes), sorted(hours)

    after = after.replace(second=0, microsecond=0)
    for ahead in range(SEARCH_DAYS + 1):
        date = after.date() + timedelta(days=ahead)
        if not day_matches(date):
            continue
        for h in hours:
            for m in minutes:
                due = datetime.combine(date, time(h, m))
                if due > after:
                    return due
    return None


_WEEKDAY_WORDS = ["Sundays", "Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays"]


def describe(schedule):
    """A schedule in plain words for the common forms ("every hour", "daily at 02:00"); else the schedule itself."""
    if not isinstance(schedule, str) or schedule_error(schedule):
        return str(schedule)
    if schedule.strip() == "@reboot":
        return "at startup"
    fields = MACROS.get(schedule.strip(), schedule).split()
    minute, hour, day, month, weekday = fields
    if fields == ["*"] * 5:
        return "every minute"
    if minute.startswith("*/") and minute[2:].isdigit() and fields[1:] == ["*"] * 4:
        return f"every {minute[2:]} minutes"
    if not minute.isdigit() or month != "*":
        return schedule
    if hour == "*" and day == "*" and weekday == "*":
        return "every hour" if minute == "0" else f"every hour at :{int(minute):02d}"
    if not hour.isdigit():
        return schedule
    at = f"{int(hour):02d}:{int(minute):02d}"
    if day == "*" and weekday == "*":
        return f"daily at {at}"
    if day == "*" and weekday.isdigit() and int(weekday) <= 7:
        return f"{_WEEKDAY_WORDS[int(weekday) % 7]} at {at}"
    if day == "*" and weekday == "1-5":
        return f"weekdays at {at}"
    if weekday == "*" and day.isdigit():
        return f"monthly on day {int(day)} at {at}"
    return schedule
