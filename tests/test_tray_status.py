"""Tests for the tray's status logic (pure Python, no Qt needed)."""

from datetime import datetime, timedelta


from signalbox.helpers import format_timestamp
from signalbox.tray_status import compute_status

NOW = datetime(2026, 11, 2, 10, 7)  # a Monday


def ts(delta):
    return format_timestamp(NOW - delta)


def status(tasks=(), groups=(), task_state=None, group_state=None, ignore_before=0):
    config = {
        "tasks": [{"name": n, "command": "true"} for n in tasks],
        "groups": [g if isinstance(g, dict) else {"name": g, "tasks": []} for g in groups],
    }
    runtime = {"tasks": task_state or {}, "groups": group_state or {}}
    return compute_status(config, runtime, ignore_before, NOW)


def test_all_passed_is_green():
    result = status(tasks=["a"], task_state={"a": {"last_run": ts(timedelta(minutes=5)), "last_status": "success"}})
    assert result["colour"] == "green"
    assert result["tooltip"] == "signalbox: all OK"
    assert result["tasks"] == [("✓", "a", "5 min ago", "success")]


def test_failed_task_is_red_until_cleared():
    state = {"a": {"last_run": ts(timedelta(minutes=5)), "last_status": "failed"}}
    assert status(tasks=["a"], task_state=state)["colour"] == "red"
    cleared = (NOW - timedelta(minutes=1)).timestamp()
    assert status(tasks=["a"], task_state=state, ignore_before=cleared)["colour"] == "green"


def test_partial_group_is_red_even_if_its_tasks_look_fine():
    # A task that failed its run-time checks never updates its own state, only the group's
    state = {"g": {"last_run": ts(timedelta(minutes=5)), "last_status": "partial"}}
    assert status(groups=["g"], group_state=state)["colour"] == "red"


def test_scheduled_group_that_missed_its_run_is_yellow():
    group = {"name": "g", "tasks": [], "schedule": "*/15 * * * *"}
    late = {"g": {"last_run": ts(timedelta(hours=3)), "last_status": "success"}}
    on_time = {"g": {"last_run": ts(timedelta(minutes=7)), "last_status": "success"}}

    result = status(groups=[group], group_state=late)
    assert result["colour"] == "yellow"
    assert result["groups"][0][0] == "⚠" and "overdue" in result["groups"][0][2]
    assert status(groups=[group], group_state=on_time)["colour"] == "green"


def test_overdue_from_an_earlier_day_names_the_day():
    group = {"name": "g", "tasks": [], "schedule": "0 12 * * *"}  # due Sunday 12:00; NOW is Monday 10:07
    state = {"g": {"last_run": ts(timedelta(days=3)), "last_status": "success"}}
    assert "was due Sun 01 Nov 12:00" in status(groups=[group], group_state=state)["groups"][0][2]


def test_long_running_group_gets_grace_for_its_run_time():
    # Due at 10:00; the last run (09:45) took 20 min, so 10:00's run may still be going at 10:07
    group = {"name": "g", "tasks": [], "schedule": "*/15 * * * *"}
    state = {"g": {"last_run": ts(timedelta(minutes=22)), "last_status": "success", "execution_time_seconds": 1200}}
    assert status(groups=[group], group_state=state)["colour"] == "green"


def test_never_run_is_shown_but_not_counted():
    group = {"name": "g", "tasks": [], "schedule": "*/15 * * * *"}
    result = status(tasks=["a"], groups=[group])
    assert result["colour"] == "green"
    assert result["tooltip"] == "signalbox: nothing has run yet"
    assert result["groups"][0][2] == "never run"


def test_failure_beats_overdue_and_tooltip_names_both():
    group = {"name": "late", "tasks": [], "schedule": "*/15 * * * *"}
    result = status(
        tasks=["bad"],
        groups=[group],
        task_state={"bad": {"last_run": ts(timedelta(minutes=1)), "last_status": "failed"}},
        group_state={"late": {"last_run": ts(timedelta(hours=3)), "last_status": "success"}},
    )
    assert result["colour"] == "red"
    assert result["tooltip"] == "signalbox: 1 failed: bad; 1 overdue: late"


def test_config_file_that_does_not_load_turns_red():
    config = {"tasks": [], "groups": [], "_load_errors": {"/home/x/config/tasks/backup.yaml": "bad YAML"}}
    result = compute_status(config, {"tasks": {}, "groups": {}}, 0, NOW)
    assert result["colour"] == "red"
    assert "cannot load backup.yaml" in result["tooltip"]


def test_malformed_config_entries_are_skipped():
    config = {"tasks": ["oops", {"command": "x"}, {"name": "a"}], "groups": [5]}
    result = compute_status(config, {"tasks": {}, "groups": {}}, 0, NOW)
    assert [row[1] for row in result["tasks"]] == ["a"]


def test_skips_are_neutral_until_they_repeat():
    state = lambda n: {
        "t": {
            "last_run": ts(timedelta(minutes=1)),
            "last_status": "skipped",  # noqa: E731
            "skip_reason": "run_if failed: mounted",
            "consecutive_skips": n,
        }
    }
    once = status(tasks=["t"], task_state=state(1))
    assert once["colour"] == "green"
    assert "skipped: run_if failed: mounted" in once["tasks"][0][2]

    config = {"tasks": [{"name": "t"}], "groups": []}
    repeated = compute_status(config, {"tasks": state(3), "groups": {}}, 0, NOW, skip_warn_after=3)
    assert repeated["colour"] == "yellow" and "skipped repeatedly: t" in repeated["tooltip"]


def test_tasks_for_another_platform_are_hidden():
    from signalbox.helpers import current_platform

    other = "linux" if current_platform() == "darwin" else "darwin"
    config = {"tasks": [{"name": "here"}, {"name": "there", "platforms": [other]}], "groups": []}
    result = compute_status(config, {"tasks": {}, "groups": {}}, 0, NOW)
    assert [row[1] for row in result["tasks"]] == ["here"]
