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

    def test_export_failure_exits_1(self, sb_home, run):
        sb_home.write_tasks([task("a")])
        sb_home.write_groups([{"name": "g", "description": "d", "tasks": ["a"]}])

        assert run("export-cron", "g").exit_code == 1  # no schedule
        assert run("export-systemd", "missing").exit_code == 1


class TestLogs:
    def test_clear_all_asks_first(self, sb_home, run):
        sb_home.write_tasks([task("a")])
        run("task", "run", "a", "-q")

        assert run("log", "clear", "--all", input="n\n").exit_code == 0
        assert len(sb_home.logs("a")) == 1

        assert run("log", "clear", "--all", input="y\n").exit_code == 0
        assert sb_home.logs("a") == []

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
