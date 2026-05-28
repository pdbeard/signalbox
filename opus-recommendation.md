# Signalbox — Critical Analysis & Recommendations

> Analysed: 31 March 2026  
> Version: 0.1.0 (Alpha)  
> Model: Claude Sonnet 4.6

---

## Executive Summary

Signalbox is a well-conceived CLI tool with a solid foundation: clean error hierarchy, file locking for log rotation, secure log-file creation (O_CREAT with 0o600), good test pass rate (211 tests, all green), and a clear separation of concerns across modules. However, several structural and design issues need addressing before the project matures, particularly around the monolithic CLI file, global mutable state, dependency bloat, and documentation drift.

---

## 1. Architecture

### 1.1 Monolithic `cli_commands.py` (Critical)

**Problem:** `cli_commands.py` is 1,080 lines and does too much — command registration, business logic (log file scanning inside `task_run`), output formatting decisions, and cross-cutting concerns like `os.environ` mutation. This violates single responsibility and makes individual commands hard to test in isolation.

**Evidence:** `task_run` contains 60+ lines of inline run-all logic including `os.listdir()` calls for discovering log files. This duplicates logic already in `log_manager`.

**Recommendation:** Split by domain into separate modules:
```
core/commands/
    task.py      # task list, task run
    group.py     # group run, group list  
    log.py       # log show, log history, log list, log tail, log clear
    config.py    # config show, config path, config validate, config check-permissions
    export.py    # export-systemd, export-cron, list-schedules
    init.py      # init
```
Each command file registers its Click commands and delegates entirely to the core modules (executor, log_manager, etc.) without containing business logic.

### 1.2 Global Mutable Singleton (High)

**Problem:** `_default_config_manager` is a module-level singleton in `config.py`. The CLI main group mutates its `._config_home` and `._global_config` attributes when `--config` is passed. This is fragile and invisible — any code that imports `get_config_value` or `load_config` at module load time will share the mutated state.

```python
# In cli_commands.py (the main group handler)
_default_config_manager._config_home = config_dir
_default_config_manager._global_config = None
```

**Recommendation:** Pass a `ConfigManager` instance through Click's `ctx.obj` (the standard Click pattern for shared state):
```python
@cli.command()
@click.pass_context
def task_run(ctx, name, ...):
    config = ctx.obj.load_config()
```
This makes state explicit and testable without module-level mutation.

### 1.3 Validator Returns Objects, Not Exceptions (Medium)

**Problem:** `validator.py` returns a `ValidationResult` object, while `AGENTS.md` and the project's documented convention state: *"raise custom exceptions from `core/exceptions.py`… Do not use result objects for error paths."* Similarly, `exporters.py` uses `ExportResult(success=False)` for error paths.

**Recommendation:** Either update the convention to acknowledge that validator/exporter are intentionally different (the result-object pattern is actually reasonable for aggregate collection of multiple errors), or migrate to raising `ValidationError` with a list of messages. The inconsistency with `ExportResult` vs. raising `ExportError` is the more urgent inconsistency to resolve.

### 1.4 Duplicate Import Organisation (Low)

**Problem:** `core/` modules mix relative and absolute imports inconsistently. `cli_commands.py` uses `from core.cli_output import ...` (absolute) while `executor.py` uses `from .config import ...` (relative). Inside command functions, `import os` appears redundantly even though `os` is already imported at the module top.

**Recommendation:** Standardise on relative imports throughout `core/`. Remove redundant `import os` inside function bodies.

---

## 2. Dependencies

### 2.1 PyQt6 as a Mandatory Dependency (Critical)

**Problem:** `pyproject.toml` lists `PyQt6>=6.4.0` as a required dependency for all users, even though it is only needed for the `signalbox-tray` entry point. Installing PyQt6 pulls in ~200MB of Qt binaries.

```toml
# Current (wrong)
dependencies = [
    "click>=8.0.0",
    "PyYAML>=5.4.0",
    "PyQt6>=6.4.0",   # ← forces Qt on CLI-only users
    "rich>=13.0.0",
]
```

**Recommendation:**
```toml
dependencies = [
    "click>=8.0.0",
    "PyYAML>=5.4.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
tray = ["PyQt6>=6.4.0"]
dev  = ["flake8>=6.0.0", "black>=23.0.0", "pytest>=7.0.0", "pytest-cov>=4.0.0"]
```
Install tray with `pipx install ".[tray]"`.

### 2.2 `pkg_resources` Usage (Medium)

**Problem:** The `init` command falls back to `pkg_resources.resource_filename()`, which is deprecated since Python 3.11 and slated for removal.

**Recommendation:** Replace with `importlib.resources`:
```python
from importlib.resources import files
template_config = files("core").joinpath("config")
```

### 2.3 Missing `pytest-cov` in Dev Dependencies (Medium)

**Problem:** `pytest-cov` is not in `[project.optional-dependencies].dev`, so `--cov` fails for all contributors. Test coverage cannot be measured.

**Recommendation:** Add `pytest-cov>=4.0.0` to the `dev` extras and document the coverage command in `AGENTS.md`/`CLAUDE.md`.

---

## 3. Code Quality

### 3.1 Flake8 Violations Across the Codebase (Medium)

Running `flake8 core/` produces 35+ violations — predominantly trailing whitespace and blank lines with whitespace (`W293`, `W291`) in `cli_commands.py`, but also substantive issues:

| File | Issue |
|------|-------|
| `core/alerts.py:6` | `get_config_value` imported but unused (`F401`) |
| `core/cli_output_tables.py:4` | `click` imported but unused (`F401`) |
| `core/cli_commands.py:657` | `task_log_dir` assigned but never used (`F841`) |
| `core/cli_commands.py:555` | `timedelta` imported but unused (`F401`) |

**Recommendation:** Run `black core/ && flake8 core/` in CI and fail the build on violations. The `dev.sh` script already has a `check` target — add it to a pre-commit hook or GitHub Actions workflow.

### 3.2 Bare `except Exception` Swallowing Issues (Medium)

Several places catch `Exception` silently and continue, which makes bugs invisible:

```python
# runtime.py — silently falls back to empty dict on any error
try:
    with open(runtime_filepath, "r") as f:
        runtime_data = yaml.safe_load(f) or {"tasks": {}}
except Exception:
    runtime_data = {"tasks": {}}
```

A YAML parsing error, a permission error, and a network error all receive identical treatment. At minimum, log these with the standard `logger` (not `click.echo`) so they appear in structured output.

### 3.3 `helpers.py` Docstring Placement Bug (Low)

In `load_yaml_files_from_dir`, an `import os` statement appears *before* the function docstring, which means the docstring is not recognised as a docstring — it is treated as a string literal:

```python
def load_yaml_files_from_dir(...) -> list:
    import os           # ← this must come after the docstring

    # Allow global suppression...
    if os.environ.get(...):
        ...
    """
    Load and merge YAML files from a directory.
    ...
    """  # ← this is unreachable as a docstring
```

**Recommendation:** Move the docstring to the top of the function and the `import os` after it (or remove the redundant `import os` since `os` is imported at module level).

### 3.4 `log_tail_cmd` Uses `subprocess.run` Without Timeout (Low)

```python
subprocess.run(["tail", f"-n{lines}", "-f", log_path])
```

`tail -f` blocks indefinitely which is intentional, but this `subprocess.run` call has no `KeyboardInterrupt` handling at the `run` call level — the `except KeyboardInterrupt` is inside the `try` for the whole block but `subprocess.run` re-raises `KeyboardInterrupt` correctly, so this is actually fine. However, `log_path` is derived from a user-provided task name looked up in config — this is safe. The concern is that on the `else` Windows branch, the infinite `while True` loop inside `with open(log_path, 'r')` will hold the file handle open indefinitely, which could interfere with log rotation on Windows (though signalbox is primarily Unix-targeted).

---

## 4. Concurrency & State Management

### 4.1 Runtime State Files Have No Write Locking (High)

**Problem:** `runtime.py`'s `save_task_runtime_state` and `save_group_runtime_state` use a read-modify-write pattern with no file locking. Two tasks running concurrently (e.g., `run --all` with a group) could race to write the same `runtime_*.yaml` file and corrupt it.

```python
# runtime.py — no locking
with open(runtime_filepath, "r") as f:
    runtime_data = yaml.safe_load(f)
# ... modify runtime_data ...
with open(runtime_filepath, "w") as f:  # ← race condition window
    yaml.dump(runtime_data, f)
```

`log_manager.py` already implements `fcntl.flock`-based locking for log rotation — the same pattern should be applied to runtime state writes.

**Recommendation:** Add `fcntl.flock(LOCK_EX)` (with a Windows fallback) around the read-modify-write cycle in both `save_task_runtime_state` and `save_group_runtime_state`, mirroring the existing `rotate_logs` implementation.

### 4.2 `ConfigManager._config_home` Is Not Thread-Safe (Medium)

The singleton `_default_config_manager._config_home` can be mutated by the `--config` flag and is also read by background threads in parallel group execution. In practice, the CLI sets `--config` once before any threads start, so this is unlikely to cause real problems today — but it's a latent bug.

---

## 5. Testing

### 5.1 No Tests for `tray_app.py` (High)

`tray_app.py` is 682 lines with meaningful logic (`_parse_last_run_to_ts`, `_human_delta`, `_load_tray_state`, `_save_tray_state`, status aggregation). None of it is tested. This is a significant blind spot.

**Recommendation:** Extract the pure logic functions from `tray_app.py` into a `core/tray_helpers.py` module (no Qt imports) so they can be unit-tested without a display. Test `_parse_last_run_to_ts`, `_human_delta`, status summarisation, and state persistence.

### 5.2 No Tests for `exporters.py` (Medium)

The systemd/cron exporter (`exporters.py`) has zero test coverage. A file like `generate_systemd_service` produces a specific string format — the generated content should be validated to ensure cron expressions and service file syntax are correct.

### 5.3 Coverage Tooling Not Set Up (Medium)

As noted in §2.3, `pytest-cov` is not in dev dependencies. Once added, the project should target ≥80% line coverage and enforce it in CI.

### 5.4 Test Isolation Relies on Patching Module-Level Globals (Medium)

Because `_default_config_manager` is a module-level singleton, tests that need different config paths must patch `core.config._default_config_manager._config_home` deep inside the import chain. The `temp_config_dir` fixture in `conftest.py` works around this by setting `SIGNALBOX_HOME`, but it's fragile — test ordering can matter.

**Recommendation:** Once the singleton is replaced with `ctx.obj` (§1.2), tests can instantiate `ConfigManager(config_home=tmp_dir)` directly without patching.

---

## 6. Documentation

### 6.1 README Commands Are Outdated (High)

The README lists these commands:
```
run-all           - Execute all scripts sequentially
run-group <name>  - Execute all scripts in a group
```

Neither `run-all` nor `run-group` exists in the current CLI. The correct commands are `task run --all` and `group run <name>`. The README also refers to "scripts" throughout when the codebase and CLI now use "tasks".

**Recommendation:** Audit the README command list against `signalbox --help` output and update. A CI check that runs `signalbox --help` and validates command names would catch future drift.

### 6.2 Demo Video Placeholder (Low)

The README contains `## DEMO VID?` — a placeholder that has never been filled. Either record a short asciicast/GIF or remove the section.

### 6.3 `AGENTS.md` and `CLAUDE.md` Partially Duplicate Each Other (Low)

Both files describe build/lint/test commands and code style. `CLAUDE.md` is more detailed and accurate (mentions `signalbox.py` as the entry point, correct architecture table). `AGENTS.md` has some drift (mentions `signalbox run <script_name>` which is not quite consistent).

**Recommendation:** Consolidate into a single `CONTRIBUTING.md` or keep only `CLAUDE.md`/`AGENTS.md` in sync with a shared source of truth section.

---

## 7. Security

### 7.1 Shell Injection Risk Is Documented but Not Validated (Medium)

`executor.py` uses `shell=True` and correctly documents this in a security note. However, there is no runtime check that validates task name characters before constructing log paths from them:

```python
# log_manager.py
os.path.join(log_dir, task_name, f"{timestamp}.log")
```

A task name containing `../` could create log files outside the log directory. Task names come from YAML config files (trusted), but the YAML schema allows arbitrary strings for `name`. The validator does not check for path-traversal characters in task names.

**Recommendation:** Add a validator check:
```python
import re
if not re.match(r'^[\w\-\.]+$', task['name']):
    file_errors.append(f"Task name '{task['name']}' contains invalid characters")
```

### 7.2 `notify-send` Presence Checked Per Call (Low)

`notifications._send_linux_notification` runs `subprocess.run(["which", "notify-send"])` on every notification. This is a minor performance issue but also means a failed `which` call is silently treated the same as `notify-send` not being installed.

**Recommendation:** Cache the result of `shutil.which("notify-send")` at module import time.

---

## 8. Packaging

### 8.1 `build/` Directory Contains Duplicate Source (Medium)

The `build/lib/` directory contains a full copy of `core/` with a nested `config/` directory. This causes confusion: `helpers.py` actually contains a special-case to skip files in `build/` directories:

```python
if 'build' in filepath.split(os.sep):
    continue
```

This is a code smell — production code should not need to know about build artefacts.

**Recommendation:** Add `build/` to `.gitignore` and `MANIFEST.in` exclusions. Remove the `build/` skip check from `helpers.py` once it is confirmed that the `build/` directory is excluded from installs.

### 8.2 Version is Hardcoded in `pyproject.toml`, Not a Single Source of Truth (Low)

`version = "0.1.0"` is set in `pyproject.toml` and retrieved via `importlib.metadata.version("signalbox")` in `cli_commands.py` (which is correct). However, there is no changelog (`CHANGELOG.md`) and no release process documented. Before moving to 0.2.0, establish a versioning and release workflow.

---

## 9. Quick Wins (Prioritised)

| Priority | Issue | Effort |
|----------|-------|--------|
| P0 | Make `PyQt6` optional (`[tray]` extra) | Small |
| P0 | README command list out of date | Small |
| P1 | Add file locking to `runtime.py` writes | Small |
| P1 | Add `pytest-cov` to dev deps, set up CI | Small |
| P1 | Fix orphaned import warnings (alerts, cli_output_tables) | Trivial |
| P1 | Replace `pkg_resources` with `importlib.resources` | Small |
| P2 | Add task name validation (path traversal) in validator | Small |
| P2 | Extract tray logic to `tray_helpers.py` for testability | Medium |
| P2 | Add tests for `exporters.py` | Medium |
| P2 | Run `black` + fix remaining flake8 violations | Small |
| P3 | Refactor `cli_commands.py` into domain modules | Large |
| P3 | Replace singleton with `ctx.obj` pattern | Medium |

---

## 10. What Is Working Well

- **Exception hierarchy** is clean and well-structured (`exceptions.py`). Exit codes are consistent.
- **Log rotation** uses `fcntl.flock` properly — thoughtful concurrency consideration.
- **Log file creation** with `os.open(..., 0o600)` avoids the TOCTOU race between creation and `chmod`.
- **`ConfigManager` class** is a genuine improvement over module-level globals and is mostly well-designed.
- **Config discovery order** (env var → XDG → user home → cwd) follows platform conventions.
- **`handle_exceptions` decorator** ensures consistent error formatting and exit codes across all CLI commands without repetition.
- **Catalog feature** allows pre-built task/group templates to be shipped with the package — good UX for new users.
- **Cross-platform notification support** (macOS + Linux) with graceful fallback is solid.
- **Test suite is fast** (211 tests in 0.31s) and all pass — excellent baseline.

---

## 11. Addendum — Current Code Check (21 May 2026)

This section preserves the original analysis above and records what still appears correct after a direct review of the current repository state.

### 11.1 Recommendations I Still Agree With

- **Global mutable config state is still a real design issue.** The CLI still mutates `_default_config_manager._config_home` and `_default_config_manager._global_config` when `--config` is passed. That means the singleton concern described in section 1.2 is still current.
- **Runtime state writes still have no locking.** `save_task_runtime_state` and `save_group_runtime_state` in `core/runtime.py` still do read-modify-write cycles without file locking, so the race described in section 4.1 remains valid.
- **PyQt6 is still mandatory for all installs.** `pyproject.toml` still lists `PyQt6>=6.4.0` in the main dependency set, so the packaging concern in section 2.1 still stands.
- **The result-object inconsistency is still present.** `validator.py` still uses `ValidationResult`, and `exporters.py` still uses `ExportResult`, while repository guidance says core modules should raise custom exceptions for error paths.
- **The `pkg_resources` fallback is still present.** The `init` command still uses a fallback to `pkg_resources.resource_filename`, so the deprecation note in section 2.2 remains accurate.
- **The helper docstring bug is still real.** In `core/helpers.py`, `load_yaml_files_from_dir` still has `import os` before the docstring, so the string is not the function docstring.
- **The `notify-send` lookup is still done per call.** `core/notifications.py` still shells out to `which notify-send` every time Linux notifications are sent.

### 11.2 Recommendations I Agree With, But Would Re-Rank

- **`cli_commands.py` still does too much, but I would not treat this as the top issue.** The file still mixes Click registration, configuration side effects, result-table assembly, and direct log file discovery. The recommendation is directionally correct, but the higher-value work is fixing behavior and packaging inconsistencies first.
- **Validator/exporter inconsistency should be split into two judgments.** I agree the codebase is inconsistent, but `ValidationResult` is a reasonable aggregate-reporting structure for validation. `ExportResult` is the sharper mismatch with the repository's stated exception-handling convention.

### 11.3 Original Claims That Are Now Stale Or Incomplete

- **The exporter test coverage claim is no longer accurate.** The repository now contains `tests/test_exporters.py`, and it covers the basic exporter code paths. The module is not untested, even if deeper coverage would still be useful.
- **The test-suite snapshot is out of date.** Current checks show about 212 collected tests, with `211 passed, 1 skipped`.
- **The flake8 count is stale.** Lint issues still exist, but the specific counts and exact findings in the original analysis reflect an earlier snapshot rather than the current repository state.

### 11.4 Additional Findings Not Captured Above

#### 11.4.1 Command Drift Is Worse Than Documentation Drift

The original document correctly noted that the README is outdated, but the issue is broader than docs alone:

- `README.md` still documents `run-all` and `run-group <name>`.
- `AGENTS.md` still documents `signalbox run-group <group_name>`.
- `core/exporters.py` still generates systemd service units with `ExecStart={signalbox_cmd} run-group {group_name}`.
- `core/exporters.py` generates cron entries with the newer `group run {group_name}` form.

This suggests an actual behavioral inconsistency in exported systemd units, not just stale documentation.

#### 11.4.2 Runtime Error Handling Is Too Broad

The original analysis noted broad exception swallowing, and that concern is especially visible in `core/runtime.py`. Runtime YAML read failures currently collapse into empty state with no logging or distinction between parse errors, missing files, and permission issues.

#### 11.4.3 Test Coverage Gap Remains For Tray Logic

I did not find a tray-specific test file, so the broader concern about untested tray logic still appears valid even though the exporter-testing claim is no longer current.

### 11.5 Updated Priority View

If prioritizing work today, I would adjust the quick-win order slightly:

| Priority | Issue | Reason |
|----------|-------|--------|
| P0 | Fix command drift across README, AGENTS, and exporter output | Prevents misleading docs and likely broken exported systemd commands |
| P0 | Make `PyQt6` optional | Removes heavy GUI dependency from CLI-only installs |
| P1 | Add locking to runtime state writes | Fixes a real correctness risk under concurrent execution |
| P1 | Clarify exception vs result-object conventions | Aligns implementation with documented repository rules |
| P1 | Replace `pkg_resources` fallback | Removes deprecated path before it becomes a compatibility issue |
| P2 | Clean up lint violations and helper/docstring issues | Low-risk quality improvement |
| P2 | Add validation for task names used in filesystem paths | Tightens path safety and config hygiene |
| P3 | Split `cli_commands.py` by domain | Good refactor, but lower urgency than correctness and packaging issues |

### 11.6 Verification Snapshot

Current local checks run against the repository:

- `pytest --collect-only -q`: about 212 collected tests
- `pytest -q`: `211 passed, 1 skipped`
- `flake8 core tests`: still reports lint issues, including unused imports and formatting/whitespace problems

### 11.7 Bottom Line

The original recommendation is broadly useful and identifies several real issues. However, parts of it are now stale, and one issue appears more serious than originally framed: the command-name drift now affects generated exporter output as well as documentation. The highest-value follow-up work is therefore command consistency, packaging cleanup, and runtime-state correctness.

---

## 12. Sonnet 4.6 Cross-Reference — 21 May 2026

This section records a line-by-line verification of the above claims against the live repository, with independent judgements on priority and framing.

### 12.1 Verified as Still Accurate

Every major claim in §11 was confirmed by direct inspection of the relevant files:

| Claim | Location |
|-------|----------|
| `cli_commands.py` is 1,080 lines | Confirmed |
| Config singleton mutated via `_default_config_manager._config_home` | `cli_commands.py:79–81` |
| `PyQt6` hard-listed in main dependencies | `pyproject.toml:32` |
| `pkg_resources` fallback still present | `cli_commands.py:179` |
| Runtime read-modify-write has no file locking (`fcntl` absent entirely) | `runtime.py` — no locking anywhere |
| `notify-send` availability checked via `subprocess.run(["which", ...])` on every call | `notifications.py:61` |
| Docstring bug confirmed: `import os` at line 20 precedes the docstring at line 25, making it unreachable as a docstring | `helpers.py:20–25` |
| Exporter command drift confirmed: systemd uses `run-group`, crontab uses `group run` | `exporters.py:127 vs :259` |
| Bare `except Exception:` in runtime state reads swallows all errors silently | `runtime.py:34, 58` |

### 12.2 Where the Framing Should Be Stronger

**The exporter drift (§11.4.1) is understated.** The document frames this as "documentation drift that also affects exporter output." The more accurate framing is that `export-systemd` generates broken service files today: `ExecStart=... run-group <name>` is not a valid signalbox command. Any user who exports a systemd timer and enables it will get silent failures when it fires. This is not a documentation problem — it is a broken feature. It should be treated as a bug fix, not a docs update.

**The runtime locking gap is real but blast radius is narrower than it sounds.** Runtime files are keyed per source config file basename (`runtime_<config>.yaml`), not a single global file. Races can only occur between tasks defined in the same YAML file running concurrently. The risk is real in `run --all`, but less likely to manifest in typical single-task invocations.

### 12.3 Where I Would Adjust the Recommendations

**Keep `ValidationResult`, convert `ExportResult`.** The document suggests resolving the result-object vs. exception inconsistency uniformly. Aggregate validation (where you want to collect *all* errors before reporting) is a legitimate use case for a result object — changing `ValidationResult` to exceptions would likely make the error-reporting worse. The sharper mismatch is `ExportResult(success=False)` for a single-operation failure, which should raise an `ExportError`. Fix `ExportResult` first; leave `ValidationResult` as-is or revisit separately.

**Tray testing gap (§5.1) is still fully open.** No tray-specific test file exists. `tray_app.py` is 682 lines. Functions like `_parse_last_run_to_ts`, `_human_delta`, `_load_tray_state`, and `_save_tray_state` are pure enough to unit test without a display. Extracting them to a `core/tray_helpers.py` module (no Qt imports) would be low effort and close a significant blind spot.

### 12.4 Adjusted Priority Order

| Priority | Issue | Reason |
|----------|-------|--------|
| **P0** | Fix `exporters.py:127` — `run-group` → `group run` in systemd `ExecStart` | Generates broken service files |
| **P0** | Make `PyQt6` optional (`[tray]` extra) | Forces ~200MB Qt onto CLI-only users |
| **P1** | Add `fcntl.flock` to `runtime.py` saves | Real race; pattern already exists in `log_manager.py` |
| **P1** | Cache `shutil.which("notify-send")` at module load | One-liner, eliminates per-call subprocess |
| **P1** | Replace `pkg_resources` with `importlib.resources` | Deprecated; small, safe change |
| **P1** | Fix docstring placement in `helpers.py:load_yaml_files_from_dir` | Misleads IDEs and `help()`; trivial to fix |
| **P2** | Add task name path-traversal validation in `validator.py` | Low effort, closes a real filesystem path hole |
| **P2** | Extract pure tray functions to `tray_helpers.py` + add tests | 682 untested lines; extraction is straightforward |
| **P2** | Remove unused imports (`alerts.py`, `cli_output_tables.py`) | Trivial cleanup |
| **P3** | Split `cli_commands.py` into domain modules | Correct direction, but lower urgency than correctness fixes |
| **P3** | Replace config singleton with `ctx.obj` pattern | Large, systemic change — do after other fixes stabilise |

### 12.5 What the Original Analysis Gets Right

The "What Is Working Well" section (§10) is accurate and worth preserving. Specific callouts that hold up on inspection:

- The `fcntl.flock` implementation in `log_manager.py` is thoughtful — the pattern just needs extending to `runtime.py`.
- The `handle_exceptions` decorator is genuinely good design: consistent error formatting and exit codes without repetition across all CLI commands.
- The exception hierarchy in `exceptions.py` is clean and consistently used.
- The test suite being fast (~212 tests in under a second) is a real asset for iteration speed.
