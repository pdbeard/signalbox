"""Tests for the shared cron parser (used by validate, the exporters and the tray)."""

from datetime import datetime

import pytest

from signalbox.cron import describe, last_due_time, next_due_time, schedule_error

NOW = datetime(2026, 11, 2, 10, 7)  # a Monday


@pytest.mark.parametrize(
    "schedule, expected",
    [
        ("*/15 * * * *", datetime(2026, 11, 2, 10, 0)),
        ("0 2 * * *", datetime(2026, 11, 2, 2, 0)),
        ("0 12 * * *", datetime(2026, 11, 1, 12, 0)),  # not yet today: yesterday's run
        ("0 9 * * 1-5", datetime(2026, 11, 2, 9, 0)),  # today, Monday, 09:00
        ("30 10 * * mon-fri", datetime(2026, 10, 30, 10, 30)),  # today's 10:30 is still ahead: Friday's
        ("0 0 * * 0", datetime(2026, 11, 1, 0, 0)),  # Sunday
        ("0 0 * * 7", datetime(2026, 11, 1, 0, 0)),  # 7 is Sunday too
        ("0 0 1 * 1", datetime(2026, 11, 2, 0, 0)),  # both day fields set: either matches (Monday)
        ("0 9 */2 * 1", datetime(2026, 10, 19, 9, 0)),  # day field starts with '*': BOTH must match (odd Monday)
        ("0 0 29 2 *", datetime(2024, 2, 29, 0, 0)),  # leap day, years back
        ("@daily", datetime(2026, 11, 2, 0, 0)),
        ("@reboot", None),  # no expected time
        ("61 * * * *", None),  # out of range: no expectation rather than a false alarm
        ("0 0 * * * *", None),  # 6 fields
    ],
)
def test_last_due_time(schedule, expected):
    assert last_due_time(schedule, NOW) == expected


@pytest.mark.parametrize(
    "schedule, error",
    [
        ("*/15 * * * *", None),
        ("@reboot", None),
        ("0 9 * jan-mar mon-fri", None),
        ("61 * * * *", "invalid minute field"),
        ("0 24 * * *", "invalid hour field"),
        ("0 0 * * 8", "invalid day-of-week field"),
        ("*/0 * * * *", "invalid minute field"),
        ("@often", "unknown macro"),
        ("0 0 * *", "expected 5 cron fields"),
    ],
)
def test_schedule_error(schedule, error):
    result = schedule_error(schedule)
    assert result is None if error is None else error in result


@pytest.mark.parametrize(
    "schedule, expected",
    [
        ("*/15 * * * *", datetime(2026, 11, 2, 10, 15)),
        ("0 * * * *", datetime(2026, 11, 2, 11, 0)),
        ("0 2 * * *", datetime(2026, 11, 3, 2, 0)),
        ("0 12 * * 1", datetime(2026, 11, 2, 12, 0)),  # today, Monday
        ("0 9 * * 0", datetime(2026, 11, 8, 9, 0)),  # next Sunday
        ("@reboot", None),
    ],
)
def test_next_due_time(schedule, expected):
    assert next_due_time(schedule, NOW) == expected


@pytest.mark.parametrize(
    "schedule, words",
    [
        ("* * * * *", "every minute"),
        ("*/10 * * * *", "every 10 minutes"),
        ("0 * * * *", "every hour"),
        ("@hourly", "every hour"),
        ("30 * * * *", "every hour at :30"),
        ("0 2 * * *", "daily at 02:00"),
        ("@daily", "daily at 00:00"),
        ("0 12 * * 1", "Mondays at 12:00"),
        ("0 9 * * 1-5", "weekdays at 09:00"),
        ("0 4 1 * *", "monthly on day 1 at 04:00"),
        ("0 9-17 * * 1-5", "0 9-17 * * 1-5"),  # not a common form: shown as written
        ("@reboot", "at startup"),
    ],
)
def test_describe(schedule, words):
    assert describe(schedule) == words
