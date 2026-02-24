# Test Suite Recommendations

## Overall State

| Metric | Count |
|--------|-------|
| Test files | 14 |
| Tests that can actually run | ~121 |
| Currently passing | 109 |
| Currently failing | 7 |
| Skipped | 5 |
| Blocked by import errors (cannot run at all) | 3 files (~109 tests) |
| Dead code — written but will never execute | ~6 tests (nested inside other functions) |

**The headline problem**: roughly half the test suite cannot run at all due to stale symbol names from a rename (`scripts` → `tasks`). All three broken files just need import lines updated — **zero production code changes required** to fix any of these issues.

---

## File-by-File Findings

---

### `test_exceptions.py` — Fix: 1 line

**Status:** 6 pass, 1 fail
**Fix effort:** Trivial

`test_script_not_found_error` references `exceptions.ScriptNotFoundError` which was renamed to `TaskNotFoundError`. Change one symbol name and the test runs correctly — it's a good test.

The other 6 tests are clean, focused, and worth keeping exactly as-is.

---

### `test_executor.py` — Fix: 2 import lines

**Status:** Import error — 0 tests run
**Fix effort:** Trivial

Two stale names in the import block:
- `ScriptNotFoundError` → `TaskNotFoundError`
- `save_script_runtime_state` is also patched in several test decorators (`@patch("core.executor.save_script_runtime_state")`) → update to `save_task_runtime_state`

The tests themselves are well structured — `TestRunTask`, `TestRunGroupParallel`, `TestRunGroupSerial` with good subprocess mocking. Worth recovering.

---

### `test_runtime.py` — Fix: 1 import line

**Status:** Import error — 0 tests run
**Fix effort:** Trivial

```python
from core.runtime import (
    load_runtime_state,
    save_script_runtime_state,   # ← rename to save_task_runtime_state
    ...
)
```

Good test coverage of save/load cycles and merge logic once unblocked.

---

### `test_cli_commands.py` — Fix: rewrite imports section

**Status:** Import error — 0 tests run
**Fix effort:** Small

The test imports CLI functions by their Python function names:
```python
from core.cli_commands import (
    list as list_cmd,    # Python function is list_shortcut
    logs,                # doesn't exist — reorganised into log subgroup
    clear_logs,          # doesn't exist at module level
    clear_all_logs,      # doesn't exist at module level
    list_groups,         # doesn't exist at module level
    show_config,         # doesn't exist at module level
    get_setting,         # doesn't exist at module level
    ...
)
```

The CLI was reorganised into subgroups (`task`, `group`, `log`, `config`) but the test file was not updated. The tests already use Click's `CliRunner` to invoke commands — they should drop the direct function imports entirely and invoke everything through `runner.invoke(cli, [...])`. No changes to production code needed.

---

### `test_alerts.py` — Fix: significant restructuring

**Status:** 11 pass, 2 fail
**Fix effort:** Medium

**Problem 1 — Dead code: 6 tests that will never run**

`test_notification_error_handling` calls `pytest.skip()` on line 119, then has ~150 lines of nested function definitions (lines 121–270) that will never execute because: (a) the skip terminates the test, and (b) even if reached, defining a function inside another test doesn't register it with pytest. Six tests are effectively invisible:

- `test_load_alerts_with_corrupt_json`
- `test_prune_alerts_by_severity_and_time`
- `test_multiple_alerts_from_single_script`
- `test_alert_summary_edge_cases`
- `test_time_based_filtering_edge_cases`
- `test_alert_retention_and_summary` (nested inside `test_save_and_load_alert`)

Several of these are genuinely useful tests. They should be moved to module level and fixed.

**Problem 2 — Stale parameter name**

`test_save_and_load_alert` and `test_load_alerts_unreadable_file` call `load_alerts(script_name=...)` but the parameter was renamed to `task_name=`.

**Problem 3 — Wrong expectation**

`test_load_alerts_unreadable_file` expects `load_alerts()` to raise `OSError` when a file is unreadable. It won't — `load_alerts()` silently skips files it can't read (the `except json.JSONDecodeError` handler). Either fix the expectation or decide whether silent skipping is the right behaviour.

**Problem 4 — Empty stub**

`test_load_alerts_filtering` is a single `pass`. Delete it or fill it in.

**The good tests** — `test_check_alert_patterns_and_save`, `test_save_alert_missing_dir`, `test_check_alert_patterns_empty`, `test_check_alert_patterns_no_pattern`, `test_check_alert_patterns_regex` — are clean, well-isolated, and worth keeping.

---

### `test_validator.py` — Fix: multiple issues

**Status:** 10 pass, 1 fail, 7 skipped
**Fix effort:** Medium

**Problem 1 — Backwards assertion**

`test_validate_configuration_valid` (line 82) patches `load_config` to return a config with a `scripts` key (the old name), then asserts that the error `'No scripts file found'` is present:

```python
# The test name says "valid" but it asserts errors exist
assert any('No scripts file found' in e for e in result.errors)
```

This is wrong on two levels: the config key is now `tasks`, and the test is asserting that a supposedly-valid configuration produces errors. The test should either assert `result.errors == []` (after fixing the key), or be renamed to reflect that it's testing an invalid/legacy config.

**Problem 2 — Stale config key throughout**

Several tests pass `{'scripts': [...], 'groups': [...]}` to the mocked `load_config` but the validator now looks for `tasks`. These tests are feeding the validator data it doesn't understand, producing unexpected errors or passing for wrong reasons.

**Problem 3 — 7 skipped tests**

Tests for duplicate detection, group reference checking, and empty file handling are skipped with notes like `"not implemented in validator"`. Before deciding to keep or delete them, check whether the validator now does implement these — if it does, remove the skips. If it doesn't, delete the tests (they're just noise in the skip count).

**Problem 4 — `assert True` as success condition**

`test_validate_empty_file` catches an exception and writes `assert True` — this always passes regardless of what happened:
```python
except Exception:
    assert True  # This is a no-op
```
Either assert something specific, or just let the exception propagate.

---

### `test_config_options.py` — Fix: update config key names

**Status:** 1 fail
**Fix effort:** Small

Fails because the CLI returns `"Unexpected error: 'tasks'"` — the test sets up a config path but the old config schema used `scripts` where the current code expects `tasks`. Updating the test fixture to use current schema should fix it.

This test does use `sys.modules` manipulation to force a module reload — that's fragile but doesn't require production code changes. It's testing real path resolution behaviour end-to-end, which is worth keeping once it's fixed.

---

### `test_config.py` — Fix: 1 test

**Status:** 53 pass, 1 fail
**Fix effort:** Small

`TestFindConfigHome::test_current_dir_fallback` fails because the developer's machine has a real `~/.config/signalbox` directory, which is found before the CWD fallback is tried. The test mocks environment variables but not the filesystem existence checks. Fix: add a mock for `os.path.isdir` / `os.path.exists` so the test doesn't depend on what's on disk.

The other 53 tests are comprehensive and pass cleanly.

---

### `test_exporters.py` — Fix: 1 assertion

**Status:** 17 pass, 1 fail
**Fix effort:** Trivial

`test_generate_cron_entry` expects the string `'run-group g1'` in the cron output but the command was updated to `group run g1`. Update the assertion string.

---

### `test_helpers.py` — No changes needed

**Status:** 4 pass
All clean. Focused tests, good use of `tmp_path`.

---

### `test_log_manager.py` — Minor note

**Status:** 12 pass, 1 skipped
Tests are in good shape. One note: the security fix that changed `write_execution_log` from `open()` to `os.open()` + `os.fdopen()` means that any test patching `builtins.open` to intercept log writes would no longer work. The skipped test (`test_write_execution_log_truncate`) should be revisited to verify it tests the right behaviour.

---

### `test_notifications.py` — No changes needed

**Status:** 11 pass
Well-written, all pass, covers platform-specific paths and error handling.

---

### `conftest.py` — No changes needed

Good fixtures using `tmp_path`-style temporary directories. One note: the docstring says the structure includes `config/scripts/` but the actual code creates `config/tasks/` — minor inconsistency in the comment only.

---

## Summary: What to Fix vs What to Delete

### Fix these (no production code changes needed in any case)

| File | Change |
|------|--------|
| `test_exceptions.py` | Rename `ScriptNotFoundError` → `TaskNotFoundError` (1 line) |
| `test_executor.py` | Rename 2 stale symbols in imports and patch decorators |
| `test_runtime.py` | Rename `save_script_runtime_state` in import (1 line) |
| `test_cli_commands.py` | Remove direct function imports; invoke all commands via `CliRunner` |
| `test_alerts.py` | Move 6 nested functions to module level; rename `script_name=` → `task_name=`; fix or remove `test_load_alerts_unreadable_file` expectation |
| `test_validator.py` | Fix key names `scripts` → `tasks`; fix backwards assertion in `test_validate_configuration_valid`; replace `assert True` in `test_validate_empty_file` |
| `test_config_options.py` | Update fixture to use current config schema |
| `test_config.py` | Mock filesystem checks in `test_current_dir_fallback` |
| `test_exporters.py` | Update assertion string `run-group` → `group run` |

### Delete these

| Test | Reason |
|------|--------|
| `test_validate_configuration_valid` | Test name and assertion are contradictory; stale schema key; the renamed `test_validate_configuration_missing_tasks` should replace it after fixing the key name |
| `test_load_alerts_filtering` | Empty `pass` body |
| `test_notification_error_handling` | Consists entirely of `pytest.skip()` plus dead nested functions; the nested tests should be extracted to module level instead |
| Validator skipped tests | Audit against current `validator.py` — if the feature exists, remove the skip; if it doesn't, delete the test |

---

## Coverage Gaps Worth Adding

These behaviours exist in the source but have no test coverage:

- **`alerts.py` — `prune_alerts()`**: the retention logic is untested (several of the dead nested tests were trying to cover this)
- **`executor.py` — parallel execution interleaving**: tests mock out most of the call stack; no test verifies that a failed parallel task doesn't block other tasks
- **`log_manager.py` — `clear_all_logs()`**: after the security fix (path resolution), there's no test verifying it resolves correctly when `log_dir` is relative
- **`cli_commands.py` — `config check-permissions`**: new command has no test
- **`config.py` — `SIGNALBOX_HOME` takes priority over `XDG_CONFIG_HOME`**: the priority ordering has no test covering every step

---

## On Your Question About Tests Requiring Production Code Changes

None of the failing or broken tests require modifying production code to make them pass. Every issue is either:
- A stale symbol name in the test import (production rename happened, test wasn't updated)
- A stale config key (`scripts` vs `tasks`) in test fixture data
- A wrong or backwards assertion
- Dead code structure (nested functions)
- Environment dependency (real config directory on disk)

The concern is valid as a principle and is confirmed here — if a test requires adding a hook, flag, or backdoor to production code just to be testable, that's a sign the test is testing the wrong thing, or the production code needs refactoring for legitimate reasons (not test-specific ones).
