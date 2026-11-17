import os
import tempfile
import pytest
import yaml
from signalbox import helpers
from signalbox.exceptions import ConfigurationError


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


def test_load_env_file_formats(tmp_path):
    f = tmp_path / "a.env"
    f.write_text(
        "# comment\n\nexport A=1\nB = two words \nC=\"quoted value\"\nD='single'\nE=has=equals\nF=$NOT_EXPANDED\n"
    )
    assert helpers.load_env_file(str(f)) == {
        "A": "1",
        "B": "two words",
        "C": "quoted value",
        "D": "single",
        "E": "has=equals",
        "F": "$NOT_EXPANDED",
    }


@pytest.mark.parametrize("line", ["NOEQUALS", "1BAD=x", "with space=x"])
def test_load_env_file_rejects_bad_lines(tmp_path, line):
    f = tmp_path / "bad.env"
    f.write_text(f"OK=1\n{line}\n")
    with pytest.raises(ConfigurationError, match="line 2"):
        helpers.load_env_file(str(f))


def test_mask_secrets_longest_first_and_ignores_short_values():
    text = "token abcd1234 and abcd and on"
    assert helpers.mask_secrets(text, ["abcd", "abcd1234", "on"]) == "token ***** and ***** and on"
