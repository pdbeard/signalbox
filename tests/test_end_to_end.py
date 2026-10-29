"""
End-to-end CLI tests against a real signalbox home on disk.

Unlike the unit tests, nothing here is mocked: commands run through the
top-level `cli` group, real shell commands execute, and assertions are made
on the files signalbox writes. Each test gets its own SIGNALBOX_HOME via the
sb_home fixture.
"""

import os

import pytest
import yaml
from click.testing import CliRunner

from signalbox.cli import cli


@pytest.fixture
def run():
    runner = CliRunner()

    def invoke(*args, **kwargs):
        return runner.invoke(cli, list(args), catch_exceptions=False, **kwargs)

    return invoke


def task(name, command="echo ok", **extra):
    return {"name": name, "description": f"{name} task", "command": command, **extra}


def runtime(sb_home, kind):
    """Merge all runtime files of one kind ('tasks' or 'groups') into a dict."""
    merged = {}
    for path in (sb_home.path / "runtime" / kind).glob("runtime_*.yaml"):
        merged.update(yaml.safe_load(path.read_text())[kind])
    return merged


class TestTaskRun:
    def test_alert_on_first_run_does_not_break_output(self, sb_home, run):
        sb_home.write_tasks([task("disk", "echo DISK FULL", alerts=[{"pattern": "FULL", "message": "full"}])])

        result = run("task", "run", "disk")

        assert result.exit_code == 0, result.output
        assert "DISK FULL" in result.output
        assert run("log", "show", "disk").exit_code == 0
        assert (sb_home.path / "logs" / "disk" / "alerts" / "alerts.jsonl").exists()

    def test_failure_exits_1_and_records_state(self, sb_home, run):
        sb_home.write_tasks([task("bad", "exit 3")])

        result = run("task", "run", "bad")

        assert result.exit_code == 1
        assert runtime(sb_home, "tasks")["bad"]["last_status"] == "failed"
        assert "Return code: 3" in sb_home.logs("bad")[0].read_text()

    def test_timeout_is_logged_and_recorded(self, sb_home, run):
        sb_home.write_tasks([task("slow", "sleep 5", timeout=1)])

        result = run("task", "run", "slow")

        assert result.exit_code == 4
        assert "timed out" in result.output
        log = sb_home.logs("slow")[0].read_text()
        assert "Return code: -9" in log and "[TIMED OUT" in log
        assert runtime(sb_home, "tasks")["slow"]["last_status"] == "failed"

    def test_timeout_still_checks_alerts_on_partial_output(self, sb_home, run):
        alert = {"pattern": "disk full", "message": "Disk full", "severity": "critical"}
        sb_home.write_tasks([task("hang", "echo CRITICAL: disk full; sleep 5", timeout=1, alerts=[alert])])

        assert run("task", "run", "hang").exit_code == 4
        assert "Disk full" in (sb_home.path / "logs" / "hang" / "alerts" / "alerts.jsonl").read_text()

    def test_undecodable_output_is_logged_not_fatal(self, sb_home, run):
        sb_home.write_tasks([task("binout", r"printf 'ok \377 done\n'")])

        result = run("task", "run", "binout")

        assert result.exit_code == 0, result.output
        log = sb_home.logs("binout")[0].read_bytes().decode("utf-8")
        assert "ok � done" in log

    def test_run_all_continues_past_a_nameless_task(self, sb_home, run):
        sb_home.write_tasks([{"description": "no name", "command": "echo x"}, task("after")])

        result = run("task", "run", "--all")

        assert result.exit_code == 1
        assert runtime(sb_home, "tasks")["after"]["last_status"] == "success"

    def test_run_all_reports_non_mapping_entry(self, sb_home, run):
        sb_home.write_tasks(["just a string", task("after")])

        result = run("task", "run", "--all")

        assert result.exit_code == 1
        # The table wraps the error column, so check both halves of the message
        assert "Task entry must be" in result.output and "mapping, got str" in result.output
        assert runtime(sb_home, "tasks")["after"]["last_status"] == "success"

    def test_each_run_gets_its_own_log_whatever_the_old_format_setting(self, sb_home, run):
        """logging.timestamp_format is gone: a coarse value used to make runs share one log file."""
        sb_home.write_settings({"logging": {"timestamp_format": "%Y"}})
        sb_home.write_tasks([task("a")])

        run("task", "run", "a", "-q")
        run("task", "run", "a", "-q")

        assert len(sb_home.logs("a")) == 2

    def test_invalid_task_is_rejected_before_running(self, sb_home, run):
        sb_home.write_tasks([{"name": "nocmd", "description": "missing command"}])

        result = run("task", "run", "nocmd")

        assert result.exit_code == 2
        assert "missing 'command'" in result.output
        assert sb_home.logs("nocmd") == []

    def test_path_traversal_task_name_is_rejected(self, sb_home, run):
        sb_home.write_tasks([task("../../escaped")])

        result = run("task", "run", "../../escaped")

        assert result.exit_code == 2
        assert "invalid" in result.output.lower()
        assert not (sb_home.path.parent / "escaped").exists()


class TestGroupRun:
    def test_all_success_exits_0(self, sb_home, run):
        sb_home.write_tasks([task("a"), task("b")])
        sb_home.write_groups([{"name": "g", "description": "d", "tasks": ["a", "b"]}])

        result = run("group", "run", "g")

        assert result.exit_code == 0, result.output
        assert runtime(sb_home, "groups")["g"]["last_status"] == "success"

    def test_stop_on_error_skips_and_exits_1(self, sb_home, run):
        sb_home.write_tasks([task("a"), task("b")])
        sb_home.write_groups([{"name": "g", "description": "d", "tasks": ["a", "b"], "stop_on_error": True}])
        assert run("group", "run", "g").exit_code == 0  # b now has a stale "success"

        sb_home.write_tasks([task("a", "false"), task("b")])
        result = run("group", "run", "g")

        assert result.exit_code == 1
        assert "skipped" in result.output
        group_state = runtime(sb_home, "groups")["g"]
        assert group_state["last_status"] == "failed"
        assert group_state["tasks_successful"] == 0

    def test_parallel_group_records_every_task(self, sb_home, run):
        names = [f"t{i}" for i in range(8)]
        sb_home.write_tasks([task(n) for n in names])
        sb_home.write_groups([{"name": "p", "description": "d", "tasks": names, "execution": "parallel"}])

        assert run("group", "run", "p").exit_code == 0
        assert sorted(runtime(sb_home, "tasks")) == names

    def test_missing_task_reference_runs_nothing(self, sb_home, run):
        sb_home.write_tasks([task("a")])
        sb_home.write_groups([{"name": "g", "description": "d", "tasks": ["a", "ghost"]}])

        result = run("group", "run", "g")

        assert result.exit_code == 2
        assert "ghost" in result.output
        assert sb_home.logs("a") == []


class TestCatalog:
    def _write_catalog_task(self, sb_home):
        catalog = sb_home.config_dir / "catalog" / "tasks"
        catalog.mkdir(parents=True)
        (catalog / "demo.yaml").write_text(yaml.dump({"tasks": [task("demo_task")]}))

    def test_catalog_not_loaded_by_default(self, sb_home, run):
        sb_home.write_tasks([task("mine")])
        self._write_catalog_task(sb_home)

        result = run("task", "list")

        assert "mine" in result.output
        assert "demo_task" not in result.output

    def test_catalog_loaded_when_enabled(self, sb_home, run):
        sb_home.write_settings({"include_catalog": True})
        sb_home.write_tasks([task("mine")])
        self._write_catalog_task(sb_home)

        assert "demo_task" in run("task", "list").output


class TestValidate:
    def test_quoted_false_stop_on_error_is_refused(self, sb_home, run):
        """'false' in quotes is a string, which Python treats as true, so it used to stop the group."""
        sb_home.write_tasks([task("bad", "exit 1"), task("good")])
        sb_home.write_groups([{"name": "g", "description": "d", "stop_on_error": "false", "tasks": ["bad", "good"]}])

        result = run("group", "run", "g")

        assert result.exit_code == 2
        assert "'stop_on_error' must be true or false" in result.output
        assert sb_home.logs("good") == []

    def test_untyped_settings_are_reported(self, sb_home, run):
        sb_home.write_settings({"execution": {"max_parallel_workers": 0}, "tray": {"poll_interval": 0}})
        sb_home.write_tasks([task("a", alerts=[{"pattern": "x", "message": "m", "notify": "false"}])])

        result = run("validate")

        assert result.exit_code == 2
        for message in ("max_parallel_workers must be", "poll_interval must be", "'notify' must be true or false"):
            assert message in " ".join(result.output.split()), message

    def test_valid_config(self, sb_home, run):
        sb_home.write_tasks([task("a")])
        sb_home.write_groups([{"name": "g", "description": "d", "tasks": ["a"], "schedule": "0 * * * *"}])

        result = run("validate")

        assert result.exit_code == 0, result.output
        assert "Configuration is valid" in result.output

    def test_errors_are_reported_per_file(self, sb_home, run):
        sb_home.write_tasks([task("a", alerts=[{"pattern": "[bad", "message": "m"}])], filename="broken.yaml")
        sb_home.write_groups([{"name": "g", "description": "d", "tasks": ["a", "ghost"], "execution": "sideways"}])

        result = run("validate")

        assert result.exit_code == 2
        assert "broken.yaml" in result.output
        assert "invalid regex pattern" in result.output
        assert "non-existent task 'ghost'" in result.output
        assert "invalid execution mode" in result.output

    def test_dotfiles_are_ignored_like_the_loader(self, sb_home, run):
        sb_home.write_tasks([task("a")])
        (sb_home.config_dir / "tasks" / ".a.yaml.swp.yaml").write_text("not: [valid")

        assert run("validate").exit_code == 0


class TestExport:
    def test_systemd_export(self, sb_home, run):
        sb_home.write_tasks([task("a")])
        sb_home.write_groups([{"name": "g", "description": "d", "tasks": ["a"], "schedule": "*/10 * * * 1-5"}])

        result = run("export-systemd", "g")

        assert result.exit_code == 0, result.output
        unit_dir = sb_home.path / "systemd" / "g"
        service = (unit_dir / "signalbox-g.service").read_text()
        assert " group run g" in service
        assert f"SIGNALBOX_HOME={sb_home.path}" in service
        assert "OnCalendar=Mon..Fri *-*-* *:0/10:00" in (unit_dir / "signalbox-g.timer").read_text()

    def test_cron_export_keeps_multiline_description_commented(self, sb_home, run):
        sb_home.write_tasks([task("a")])
        sb_home.write_groups([{"name": "g", "description": "line one\nline two", "tasks": ["a"], "schedule": "@daily"}])

        assert run("export-cron", "g").exit_code == 0
        lines = (sb_home.path / "cron" / "g" / "g.cron").read_text().splitlines()
        assert lines[0] == "# line one line two"
        assert len(lines) == 2

    def test_export_failure_exits_1(self, sb_home, run):
        sb_home.write_tasks([task("a")])
        sb_home.write_groups([{"name": "g", "description": "d", "tasks": ["a"]}])

        assert run("export-cron", "g").exit_code == 1  # no schedule
        assert run("export-systemd", "missing").exit_code == 1


class TestLogs:
    def test_bracketed_output_is_shown_literally(self, sb_home, run):
        """Rich must not read task output or descriptions as markup ('[/x]' used to crash log list)."""
        sb_home.write_tasks([task("cp", "echo synced to [/mnt/backup]", description="copy [red]files[/red]")])
        run("task", "run", "cp", "-q")

        for args in (("log", "list"), ("log", "list", "-v")):
            result = run(*args)
            assert result.exit_code == 0, result.output
            assert "[/mnt/backup]" in result.output
        assert "copy [red]files[/red]" in run("list").output

    def test_clear_all_asks_first(self, sb_home, run):
        sb_home.write_tasks([task("a")])
        run("task", "run", "a", "-q")

        assert run("log", "clear", "--all", input="n\n").exit_code == 0
        assert len(sb_home.logs("a")) == 1

        assert run("log", "clear", "--all", input="y\n").exit_code == 0
        assert sb_home.logs("a") == []

    def test_clear_task_also_clears_its_alerts(self, sb_home, run):
        sb_home.write_tasks([task("a", "echo FAIL", alerts=[{"pattern": "FAIL", "message": "failed"}])])
        run("task", "run", "a", "-q")
        assert "failed" in run("alerts", "a").output

        assert run("log", "clear", "--task", "a").exit_code == 0
        assert sb_home.logs("a") == []
        assert "No alerts found" in run("alerts", "a").output

    def test_list_filters_by_status_with_limit(self, sb_home, run):
        sb_home.write_tasks([task("good"), task("bad", "false")])
        for _ in range(3):
            run("task", "run", "good", "-q")
        run("task", "run", "bad", "-q")

        result = run("log", "list", "--failed", "--last", "5")

        assert "Total: 1 log(s)" in result.output
        assert "bad" in result.output

    def test_tail_no_follow(self, sb_home, run):
        sb_home.write_tasks([task("a", "echo tail-me")])
        run("task", "run", "a", "-q")

        result = run("log", "tail", "a", "--no-follow")

        assert result.exit_code == 0
        assert "tail-me" in result.output


class TestCheckPermissions:
    def test_clean_home_passes(self, sb_home, run):
        sb_home.write_tasks([task("a")])
        for root, dirs, files in os.walk(sb_home.path):
            os.chmod(root, 0o700)
            for f in files:
                os.chmod(os.path.join(root, f), 0o600)

        result = run("config", "check-permissions")

        assert result.exit_code == 0, result.output

    def test_writable_global_config_and_task_dir_are_flagged(self, sb_home, run):
        sb_home.write_tasks([task("a")])
        os.chmod(sb_home.path, 0o700)
        os.chmod(sb_home.config_dir / "signalbox.yaml", 0o666)
        os.chmod(sb_home.config_dir / "tasks", 0o777)

        result = run("config", "check-permissions")

        assert result.exit_code == 1
        assert "signalbox.yaml" in result.output
        assert "Task directory" in result.output


class TestTaskEnvironment:
    def test_default_working_directory_is_signalbox_home(self, sb_home, run, tmp_path, monkeypatch):
        sb_home.write_tasks([task("where", "pwd -P")])
        monkeypatch.chdir(tmp_path)  # where the user happens to be must not matter

        result = run("task", "run", "where")

        assert result.exit_code == 0
        assert os.path.realpath(sb_home.path) in result.output

    def test_task_cwd_relative_to_home(self, sb_home, run):
        (sb_home.path / "work").mkdir()
        sb_home.write_tasks([task("where", "pwd -P", cwd="work")])

        result = run("task", "run", "where")

        assert os.path.realpath(sb_home.path / "work") in result.output

    def test_missing_cwd_is_an_error(self, sb_home, run):
        sb_home.write_tasks([task("where", "pwd", cwd="does-not-exist")])

        result = run("task", "run", "where")

        assert result.exit_code == 2
        assert "does not exist" in result.output

    def test_stdin_is_not_inherited(self, sb_home, run):
        sb_home.write_tasks([task("reader", "read line || echo no-stdin")])

        result = run("task", "run", "reader", input="SECRET\n")

        assert "no-stdin" in result.output
        assert "SECRET" not in sb_home.logs("reader")[0].read_text()


class TestRunTimeValidation:
    def test_missing_description_still_runs(self, sb_home, run):
        sb_home.write_tasks([{"name": "nodesc", "command": "echo ran"}])

        result = run("task", "run", "nodesc")

        assert result.exit_code == 0
        assert "ran" in result.output
        assert run("validate").exit_code == 2  # still reported by validate

    def test_alerts_mapping_is_rejected_before_running(self, sb_home, run):
        # 'alerts:' written as a mapping instead of a list (missing '-')
        sb_home.write_tasks([task("a", "touch ran", alerts={"pattern": "x", "message": "m"})])

        result = run("task", "run", "a")

        assert result.exit_code == 2
        assert "alerts field must be a list" in result.output
        assert not (sb_home.path / "ran").exists()

    def test_bad_alert_pattern_does_not_block_run(self, sb_home, run):
        sb_home.write_tasks([task("a", "echo ok", alerts=[{"pattern": "[bad", "message": "m"}])])

        result = run("task", "run", "a")

        assert result.exit_code == 0
        assert "Invalid alert pattern" in result.output


class TestLogRotation:
    def test_size_rotation_keeps_logs_within_limit(self, sb_home, run):
        # ~0.4 MB of output per run with a 1 MB limit: at most 2-3 logs survive
        sb_home.write_tasks([task("big", "yes x | head -c 400000", log_limit={"type": "size", "value": 1})])

        for _ in range(6):
            run("task", "run", "big", "-q")

        logs = sb_home.logs("big")
        assert 1 <= len(logs) <= 3
        assert sum(p.stat().st_size for p in logs) <= 1024 * 1024

    def test_validate_rejects_unknown_log_limit_type(self, sb_home, run):
        sb_home.write_tasks([task("a", log_limit={"type": "megabytes", "value": 1})])

        result = run("validate")

        assert result.exit_code == 2
        assert "log_limit type must be one of count, age, size" in result.output


class TestConfigOption:
    def test_config_file_selects_its_home(self, sb_home, run, tmp_path, monkeypatch):
        monkeypatch.setenv("SIGNALBOX_HOME", str(tmp_path / "elsewhere"))
        sb_home.write_tasks([task("a")])

        result = run("--config", str(sb_home.config_dir / "signalbox.yaml"), "run", "a")

        assert result.exit_code == 0, result.output

    def test_config_file_outside_config_dir_is_rejected(self, sb_home, run, tmp_path):
        custom = tmp_path / "custom.yaml"
        custom.write_text("execution:\n  default_timeout: 77\n")

        result = run("--config", str(custom), "config", "show")

        assert result.exit_code == 2
        assert "expected <home>/config/signalbox.yaml" in result.output


class TestAlertRetention:
    def test_default_keeps_critical_alerts_for_90_days(self, sb_home, run):
        """Without an alerts.retention section the shipped per-severity defaults apply."""
        from datetime import datetime, timedelta
        import json

        from signalbox.helpers import format_timestamp

        sb_home.write_tasks([task("a")])
        alerts_dir = sb_home.path / "logs" / "a" / "alerts"
        alerts_dir.mkdir(parents=True)
        old = format_timestamp(datetime.now() - timedelta(days=60))
        (alerts_dir / "alerts.jsonl").write_text(
            json.dumps({"pattern": "p", "severity": "critical", "timestamp": old}) + "\n"
        )

        assert run("task", "run", "a").exit_code == 0
        assert old in (alerts_dir / "alerts.jsonl").read_text()


class TestAlertCooldown:
    def test_repeated_alert_notifies_once_within_cooldown(self, sb_home, run, monkeypatch):
        from signalbox import notifications

        sent = []
        monkeypatch.setattr(notifications, "send_notification", lambda **kw: sent.append(kw) or True)
        sb_home.write_settings({"alerts": {"notifications": {"enabled": True}}})
        sb_home.write_tasks(
            [task("disk", "echo FULL", alerts=[{"pattern": "FULL", "message": "full", "severity": "warning"}])]
        )

        for _ in range(3):
            run("task", "run", "disk", "-q")

        assert len(sent) == 1
        lines = (sb_home.path / "logs" / "disk" / "alerts" / "alerts.jsonl").read_text().splitlines()
        assert len(lines) == 3  # every occurrence is still recorded

    def test_cooldown_zero_notifies_every_run(self, sb_home, run, monkeypatch):
        from signalbox import notifications

        sent = []
        monkeypatch.setattr(notifications, "send_notification", lambda **kw: sent.append(kw) or True)
        sb_home.write_settings({"alerts": {"notifications": {"enabled": True, "cooldown_minutes": 0}}})
        sb_home.write_tasks(
            [task("disk", "echo FULL", alerts=[{"pattern": "FULL", "message": "full", "severity": "warning"}])]
        )

        for _ in range(3):
            run("task", "run", "disk", "-q")

        assert len(sent) == 3


class TestSystemdUnits:
    def _export(self, sb_home, run, *flags):
        sb_home.write_tasks([task("a")])
        sb_home.write_groups([{"name": "g", "description": "line one\nline two", "tasks": ["a"], "schedule": "@daily"}])
        assert run("export-systemd", "g", *flags).exit_code == 0
        return (sb_home.path / "systemd" / "g" / "signalbox-g.service").read_text()

    def test_system_unit_runs_as_exporting_user(self, sb_home, run):
        import getpass

        service = self._export(sb_home, run)

        assert f"User={getpass.getuser()}" in service
        assert "[Install]" not in service  # started by the timer
        assert "Description=signalbox - line one line two" in service

    def test_user_unit_has_no_user_directive(self, sb_home, run):
        service = self._export(sb_home, run, "--user")

        assert "User=" not in service
