import pytest
from unittest.mock import patch


def test_rotate_by_count(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    # Create 5 files with increasing mtime
    files = []
    for i in range(5):
        f = d / f"f{i}.log"
        f.write_text("x")
        os.utime(f, (1000 + i, 1000 + i))
        files.append(f)
    log_manager._rotate_by_count(str(d), [f.name for f in files], 2)
    remaining = list(d.iterdir())
    assert len(remaining) == 2


def test_rotate_by_age(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    # Create 2 old, 2 new files
    old = d / "old.log"
    old.write_text("x")
    os.utime(old, (1000, 1000))
    new = d / "new.log"
    new.write_text("x")
    os.utime(new, None)
    log_manager._rotate_by_age(str(d), [old.name, new.name], 1)  # 1 day
    files = list(d.iterdir())
    assert new in files and old not in files


def test_get_latest_log(tmp_path, monkeypatch):
    monkeypatch.setattr(log_manager, "get_task_log_dir", lambda name: str(tmp_path))
    f1 = tmp_path / "a.log"
    f2 = tmp_path / "b.log"
    f1.write_text("x")
    f2.write_text("y")
    os.utime(f1, (1000, 1000))
    os.utime(f2, (2000, 2000))
    path, exists = log_manager.get_latest_log("foo")
    assert exists and path.endswith("b.log")


def test_get_log_history(tmp_path, monkeypatch):
    monkeypatch.setattr(log_manager, "get_task_log_dir", lambda name: str(tmp_path))
    f1 = tmp_path / "a.log"
    f2 = tmp_path / "b.log"
    f1.write_text("x")
    f2.write_text("y")
    os.utime(f1, (1000, 1000))
    os.utime(f2, (2000, 2000))
    info, exists = log_manager.get_log_history("foo")
    assert exists and info[0][0] == "b.log"


def test_log_listing_ignores_alerts_dir_and_lock(tmp_path, monkeypatch):
    """The alerts/ subdirectory and rotation lock share the log dir but are not logs."""
    monkeypatch.setattr(log_manager, "get_task_log_dir", lambda name: str(tmp_path))
    log = tmp_path / "a.log"
    log.write_text("x")
    os.utime(log, (1000, 1000))
    (tmp_path / "alerts").mkdir()
    (tmp_path / ".rotate.lock").write_text("")
    path, exists = log_manager.get_latest_log("foo")
    assert exists and path.endswith("a.log")
    info, exists = log_manager.get_log_history("foo")
    assert [name for name, _ in info] == ["a.log"]


def test_clear_script_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(log_manager, "get_task_log_dir", lambda name: str(tmp_path))
    f1 = tmp_path / "a.log"
    f1.write_text("x")
    assert log_manager.clear_task_logs("foo")
    assert not list(tmp_path.iterdir())


def test_clear_all_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(log_manager, "get_resolved_log_dir", lambda: str(tmp_path))
    d = tmp_path / "foo"
    (d / "alerts").mkdir(parents=True)
    (d / "a.log").write_text("x")
    (d / "alerts" / "alerts.jsonl").write_text("{}")
    assert log_manager.clear_all_logs()
    assert not (d / "a.log").exists()
    assert not (d / "alerts" / "alerts.jsonl").exists()


def test_clear_all_logs_leaves_other_files(tmp_path, monkeypatch):
    """Only logs and alert history are removed, even if log_dir points somewhere broad."""
    monkeypatch.setattr(log_manager, "get_resolved_log_dir", lambda: str(tmp_path))
    (tmp_path / "notes.txt").write_text("keep")
    (tmp_path / "project").mkdir()
    (tmp_path / "project" / "main.py").write_text("keep")
    (tmp_path / "project" / "run.log").write_text("x")
    assert log_manager.clear_all_logs()
    assert (tmp_path / "notes.txt").exists()
    assert (tmp_path / "project" / "main.py").exists()


def test_format_log_with_colors():
    content = "Command: echo hi\nReturn code: 0\nSTDOUT:\nhi\nSTDERR:\n"
    colors = [color for _, color in log_manager.format_log_with_colors(content)]
    assert colors == ["blue", "green", "blue", None, "blue", None]


def test_format_log_with_colors_failure():
    content = "Return code: 1\n[TIMED OUT after 5s]\n[OUTPUT TRUNCATED - exceeded 5.0MB limit]"
    colors = [color for _, color in log_manager.format_log_with_colors(content)]
    assert colors == ["red", "red", "yellow"]
    assert all(color is None for _, color in log_manager.format_log_with_colors(content, show_colors=False))


@pytest.mark.parametrize(
    "marker",
    ["[STDOUT TRUNCATED - 10 bytes removed]", "[STDERR TRUNCATED]", "[COMMAND TRUNCATED]", "[STDOUT OMITTED - x]"],
)
def test_format_log_with_colors_truncation_markers(marker):
    """Every truncation marker the writer emits is highlighted, not just the legacy one."""
    assert log_manager.format_log_with_colors(marker) == [(marker, "yellow")]


import os
import tempfile
import shutil
import pytest
from signalbox import log_manager


def test_get_task_log_dir(monkeypatch):
    monkeypatch.setattr(log_manager, "get_resolved_log_dir", lambda: "/home/u/logs")
    assert log_manager.get_task_log_dir("mytask") == "/home/u/logs/mytask"


@pytest.mark.parametrize("name", ["../escape", "a/b", "..", ".hidden", "-flag", "", None])
def test_get_task_log_dir_rejects_unsafe_names(monkeypatch, name):
    from signalbox.exceptions import ConfigurationError

    monkeypatch.setattr(log_manager, "get_resolved_log_dir", lambda: "/home/u/logs")
    with pytest.raises(ConfigurationError):
        log_manager.get_task_log_dir(name)


def test_ensure_log_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(log_manager, "get_resolved_log_dir", lambda: str(tmp_path))
    task_name = "testtask"
    log_dir = os.path.join(tmp_path, task_name)
    if os.path.exists(log_dir):
        shutil.rmtree(log_dir)
    log_manager.ensure_log_dir(task_name)
    assert os.path.isdir(log_dir)


def test_get_log_path(monkeypatch):
    monkeypatch.setattr(log_manager, "get_resolved_log_dir", lambda: "/home/u/logs")
    path = log_manager.get_log_path("mytask", "20260126_120000")
    assert path == "/home/u/logs/mytask/20260126_120000.log"


def test_write_execution_log(tmp_path, monkeypatch):
    monkeypatch.setattr(log_manager, "get_config_value", lambda k, d=None: 1)  # 1MB
    log_file = os.path.join(tmp_path, "log.txt")
    command = "echo 1"
    return_code = 0
    stdout = "output"
    stderr = ""
    log_manager.write_execution_log(log_file, command, return_code, stdout, stderr)
    assert os.path.exists(log_file)
    with open(log_file) as f:
        content = f.read()
    assert "echo 1" in content and "output" in content


class TestLogSizeBudget:
    """The size cap must bound the whole file, not each stream separately."""

    @staticmethod
    def _write(tmp_path, command, stdout, stderr, mb):
        settings = {
            "logging.max_file_size_mb": mb,
            "logging.include_command": True,
            "logging.include_return_code": True,
            "execution.capture_stdout": True,
            "execution.capture_stderr": True,
        }
        log_file = tmp_path / "out.log"
        with patch.object(log_manager, "get_config_value", lambda p, d=None: settings.get(p, d)):
            log_manager.write_execution_log(str(log_file), command, 0, stdout, stderr)
        return log_file

    @pytest.mark.parametrize(
        "command,stdout,stderr",
        [
            ("cmd", "x" * 5_000_000, "y" * 5_000_000),  # both streams oversized
            ("c" * 2_000_000, "out", "err"),  # command alone exceeds the cap
            ("cmd", "x" * 3_000_000, ""),  # stdout only
            ("cmd", "", "e" * 3_000_000),  # stderr only
        ],
    )
    def test_file_never_exceeds_configured_cap(self, tmp_path, command, stdout, stderr):
        log_file = self._write(tmp_path, command, stdout, stderr, mb=1)
        assert log_file.stat().st_size <= 1 * 1024 * 1024

    def test_oversized_command_still_keeps_output(self, tmp_path):
        """A huge command must not silently discard the task's actual output."""
        log_file = self._write(tmp_path, "c" * 2_000_000, "IMPORTANT-OUTPUT", "", mb=1)
        assert "IMPORTANT-OUTPUT" in log_file.read_text()

    def test_truncation_is_marked(self, tmp_path):
        """Truncated output says so, so a partial log is never mistaken for a full one."""
        log_file = self._write(tmp_path, "cmd", "x" * 5_000_000, "y" * 5_000_000, mb=1)
        content = log_file.read_text()
        assert "STDOUT TRUNCATED" in content
        assert "STDERR TRUNCATED" in content

    def test_small_output_is_untouched(self, tmp_path):
        """Output well within the cap is written verbatim."""
        log_file = self._write(tmp_path, "echo hi", "hello\n", "", mb=5)
        content = log_file.read_text()
        assert "hello" in content
        assert "TRUNCATED" not in content

    @pytest.mark.parametrize("cap_bytes", [300, 400, 600, 1000])
    def test_tiny_cap_is_bounded_and_marked(self, tmp_path, cap_bytes):
        """Even when there is no room for head and tail, truncation is flagged."""
        log_file = self._write(tmp_path, "c" * 500, "x" * 5000, "y" * 5000, mb=cap_bytes / (1024 * 1024))
        content = log_file.read_text()
        assert log_file.stat().st_size <= cap_bytes
        for label, original in (("STDOUT", "x" * 5000), ("STDERR", "y" * 5000)):
            if original not in content:
                assert f"{label} TRUNCATED" in content or f"{label} OMITTED" in content

    @pytest.mark.parametrize("char", ["é", "€", "😀"])
    def test_cap_counts_bytes_not_characters(self, tmp_path, char):
        """Multi-byte output must not overshoot the cap, which is a size on disk."""
        log_file = self._write(tmp_path, f"echo {char}", char * 2_000_000, char * 2_000_000, mb=1)
        assert log_file.stat().st_size <= 1 * 1024 * 1024
        # Cuts never split a character, so the file is still valid UTF-8.
        content = log_file.read_bytes().decode("utf-8")
        assert "STDOUT TRUNCATED" in content and "STDERR TRUNCATED" in content

    def test_unencodable_output_is_still_logged(self, tmp_path):
        """A lone surrogate (from undecodable task output) must not stop the log being written."""
        log_file = self._write(tmp_path, "cmd", "before \udcff after", "", mb=1)
        content = log_file.read_bytes().decode("utf-8")
        assert "before" in content and "after" in content
