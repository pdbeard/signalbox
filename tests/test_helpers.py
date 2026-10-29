import os
import tempfile
import pytest
import yaml
from signalbox import helpers


def test_load_yaml_files_from_dir(tmp_path):
    d = tmp_path / "yamls"
    d.mkdir()
    f1 = d / "a.yaml"
    f2 = d / "b.yaml"
    f1.write_text("tasks:\n- name: t1")
    f2.write_text("tasks:\n- name: t2")
    items = helpers.load_yaml_files_from_dir(str(d), "tasks")
    assert [(i["data"]["name"], os.path.basename(i["source"])) for i in items] == [("t1", "a.yaml"), ("t2", "b.yaml")]


def test_load_yaml_files_from_dir_under_build_directory(tmp_path):
    """A config home inside a directory named 'build' must still load."""
    d = tmp_path / "build" / "config" / "tasks"
    d.mkdir(parents=True)
    (d / "a.yaml").write_text("tasks:\n- name: t1")
    assert [i["data"]["name"] for i in helpers.load_yaml_files_from_dir(str(d), "tasks")] == ["t1"]


def test_format_timestamp():
    from datetime import datetime

    ts = helpers.format_timestamp(datetime(2026, 1, 26, 12, 0, 0))
    assert "20260126" in ts
