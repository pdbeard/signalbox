import os
import tempfile
import pytest
import yaml
from core import helpers

def test_load_yaml_files_from_dir(tmp_path):
    d = tmp_path / 'yamls'
    d.mkdir()
    f1 = d / 'a.yaml'
    f2 = d / 'b.yaml'
    f1.write_text('scripts:\n- name: s1')
    f2.write_text('scripts:\n- name: s2')
    items = helpers.load_yaml_files_from_dir(str(d), 'scripts')
    assert any(i['name'] == 's1' for i in items)
    assert any(i['name'] == 's2' for i in items)

def test_load_yaml_files_from_dir_track_sources(tmp_path):
    d = tmp_path / 'yamls'
    d.mkdir()
    f1 = d / 'a.yaml'
    f1.write_text('scripts:\n- name: s1')
    items = helpers.load_yaml_files_from_dir(str(d), 'scripts', track_sources=True)
    assert isinstance(items[0], dict) and 'data' in items[0] and 'source' in items[0]

def test_load_yaml_files_from_dir_filter(tmp_path):
    d = tmp_path / 'yamls'
    d.mkdir()
    (d / 'a.yaml').write_text('scripts:\n- name: s1')
    (d / 'b.yaml').write_text('scripts:\n- name: s2')
    items = helpers.load_yaml_files_from_dir(str(d), 'scripts', filter_func=lambda f: f == 'a.yaml')
    assert any(i['name'] == 's1' for i in items)
    assert not any(i['name'] == 's2' for i in items)

def test_format_timestamp():
    from datetime import datetime
    ts = helpers.format_timestamp(datetime(2026, 1, 26, 12, 0, 0))
    assert '20260126' in ts
