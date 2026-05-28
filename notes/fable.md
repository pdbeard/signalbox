# Fable Review — Signalbox

*An analysis of the codebase, project direction, and overall value. July 2026.*

## Snapshot

Signalbox is a ~4,600-line Python CLI (plus PyQt6 tray app) for defining shell tasks in YAML, running them individually or in groups (serial/parallel), logging every run, matching alert patterns against output, and exporting systemd/cron configs for scheduling. 91 commits, single author, v0.1.0 alpha. The test suite is healthy: **211 tests pass in 0.35s**.

## The Verdict Up Front

**The code is in better shape than most solo alpha projects — the documentation and packaging are what's holding it back.** The core engine (config → validate → execute → log → alert → runtime state) is cleanly layered, tested, and shows real attention to security details (0o600 log files, atomic writes, permission checks, timeout floors). But the README describes a CLI that no longer exists, the package installs under the name `core`, and PyQt6 is a hard dependency of what is fundamentally a CLI tool. Those three things would sink a first impression from any outside user, and all three are cheap to fix.

**Is it worth continuing?** Yes, with a caveat about ambition. See "Direction" below.

---

## Code Analysis

### What's good

- **Clean module boundaries.** `executor.py`, `log_manager.py`, `alerts.py`, `runtime.py`, `config.py` each do one thing. The execution flow in `executor.py` (`_find_task` → `_execute` → `_post_execution`) is easy to follow and the docstrings state what raises what.
- **Real security thinking, honestly documented.** `shell=True` is a deliberate, documented trade-off (SECURITY.md, header comment in executor.py). Log files are created 0o600 with no chmod window (`log_manager.py:66`), config writes are atomic temp-file-and-rename (`config.py:249`, `tray_app.py:81`), and `config check-permissions` exists. This is more care than most cron-wrapper projects show.
- **Exceptions and exit codes are designed, not accidental.** The `handle_exceptions` decorator (`cli_commands.py:21`) maps exception types to POSIX-ish exit codes consistently.
- **Good test hygiene.** 211 fast tests across every core module, with a `conftest.py` and per-module test files. This is the asset that makes everything else fixable.
- **ConfigManager class with backward-compatible module functions** (`config.py`) — the right transitional pattern away from module globals.

### Bugs and issues found

1. **Log directory lookup bug in `task run --all` and `group run`.** `cli_commands.py:351` and `cli_commands.py:430` do `config.get("paths", {}).get("log_dir", "logs")` — but `config` there is the tasks/groups dict from `load_config()`, which never contains a `paths` key. It always falls back to `"logs"` relative to the *current working directory*, while logs are actually written relative to config home (`log_manager.py:get_task_log_dir`). Run these commands from anywhere but the config home and the "Log File" column comes up empty or wrong. Fix: use `log_manager.get_task_log_dir()` in both places.

2. **Package installs as `core`.** `pyproject.toml` declares `packages = ["core"]`, so `pip install signalbox` puts a package literally named `core` into site-packages. That's a namespace collision waiting to happen with any other package (or user code) named `core`, and it's a hard blocker for PyPI publication. Rename the package directory to `signalbox/` (and the current `signalbox.py` shim to a `__main__.py` or console-script entry).

3. **PyQt6 is a hard dependency.** ~100MB of Qt to install a CLI cron-wrapper. Move it to an optional extra (`pip install signalbox[tray]`) and import it lazily in `tray_app.py` with a friendly error. This alone will dramatically improve install experience on servers — which is exactly where a script-monitoring tool wants to live.

4. **Inconsistent fallback defaults.** `write_execution_log` falls back to `max_file_size_mb: 100` (`log_manager.py:53`) while the shipped config says 5. If the config key is missing, behavior silently differs 20x from the documented default. Keep code fallbacks identical to shipped config values (same pattern worth auditing everywhere `get_config_value` is called with a literal default).

5. **CLI reaches into private state.** The `-c/--config` option sets `_default_config_manager._config_home` and `._global_config` directly (`cli_commands.py:79`), and `tray_app.py` imports `_default_config_manager` too. Add a public `set_config_home()` method; private-attribute pokes from other modules are how the ConfigManager refactor unravels.

6. **`log tail` can wait forever.** The wait loop at `cli_commands.py:658` polls every 0.5s with no timeout and (on the non-Windows path) hands off to `tail -f` ignoring the `--lines`-after-wait edge case. Minor, but an easy Ctrl+C-only trap.

7. **`cli_commands.py` is becoming the junk drawer** (1,080 lines, and the header comment in CLAUDE.md already undersells it). The command *groups* are well-organized — split the file along those exact lines: `commands/task.py`, `commands/group.py`, `commands/log.py`, `commands/config.py`. Mechanical refactor, big readability payoff.

8. **Scattered inline imports** (`import os` mid-function in several commands, `from core.cli_output import ...` inside functions). Some are deliberate lazy-loads (rich, PyQt) — fine. The stdlib ones are just noise; hoist them.

### Not bugs, but worth knowing

- Parallel group execution mutates the shared `config` dict from worker threads (`task["last_status"] = status` in `executor.py:118`). Each thread touches only its own task's dict so it's safe today, but it's fragile — a comment or a return-value-based design would protect it.
- `run_shortcut` and `task_run` set `os.environ["SIGNALBOX_SUPPRESS_CONFIG_WARNINGS"]` *and* pass `suppress_warnings=True` — one mechanism should win.

---

## Usability

**The CLI design itself is good.** The noun-verb structure (`task run`, `log show`, `group list`) with root-level shortcuts (`run`, `list`, `validate`) is the right modern pattern, rich tables look professional, and `validate` giving a summary panel is a genuinely nice touch.

**The documentation actively fights the tool.** This is the single biggest usability problem:

- The README's command list is the *old* CLI: `run-group`, `list-groups`, `logs <name>`, `log-history`, `clear-logs`, `show-config`, `get-setting` — none of these exist anymore. A new user following the README fails at step one.
- The README still says "scripts" everywhere; the codebase renamed to "tasks" many commits ago. Its group examples use a `scripts:` key, but `group run` reads `group["tasks"]` (`cli_commands.py:416`) — copy-pasting the README's own example produces a KeyError.
- The README has a visibly corrupted section (line 117: a stray `` `** - Group definitions...`` fragment mid-command-list), a `## DEMO VID?` placeholder, and links to a `CONFIG_REFERENCE.md` that doesn't exist.
- `init` creates `config/tasks/`... while the README says it creates `config/scripts/`.

Rewriting the README against the actual CLI is a half-day task and probably the highest-leverage half-day available in this repo.

**Repo hygiene:** the root directory carries ~10 planning/AI-review artifacts (`team-review-summary.md`, `opus-recommendation.md`, `basic-review-summary-old.md`, `claude_suggestions.md`, `test_recommendation.md`, `todo`, `issues`, `AGENTS.md.bak`, `taskbar.md`, `Brainstorm.md`...). Individually harmless; collectively they make the project look like a scratchpad. Move keepers into `notes/` or `docs/dev/`, delete the stale ones, and gitignore future ones. (Yes, this file adds to the pile — feel free to relocate it too.)

---

## Direction & "Is It Worth It?"

**The honest competitive picture:** this space is crowded. Plain systemd timers + `OnFailure=`, cron + `chronic`, healthchecks.io/cronitor (dead-man's-switch SaaS), Jobber, Ofelia, and full schedulers like Airflow all overlap with parts of Signalbox. Signalbox will not out-feature any of them.

**But it doesn't need to.** Signalbox's actual niche is real and underserved: *"I'm one person with a handful of machines and a dozen shell scripts, I want them in version-controllable YAML, I want to see red/green in my tray, and I don't want a daemon, a database, or a SaaS account."* The design decisions already made — no built-in scheduler (export to systemd/cron instead), write-once logs, plain files for state — are exactly right for that niche. They keep the tool boring in the best way. **Keep that discipline.**

Specific direction calls:

1. **Shelve the distributed/multi-host vision** (`Brainstorm.md`) for now. REST APIs, mTLS, discovery, relay servers — that's a different, much larger product with a real security surface, being bolted onto a tool that hasn't shipped v0.1 to a single external user. The moment Signalbox listens on a socket, the current "config files must be trusted" security model collapses and everything gets harder. If multi-host is ever pursued, the cheap 80% version is: tray app reads runtime-state files synced by something that already exists (syncthing/SSH/NFS). File format as API — very Signalbox.

2. **The tray app + alerting is the differentiator — invest there.** Nothing else in this space gives a local, no-daemon, glanceable status light. "Next scheduled run" display, alert history in the tray, and a `signalbox doctor` (config valid? permissions ok? timers actually installed and firing?) would each strengthen the wedge more than any new execution feature.

3. **Finish the good ideas already on the todo list:** per-task timeout override and size-based log rotation are both small, obviously right, and consistent with the tool's shape.

4. **Ship it.** Fix the package name, make Qt optional, rewrite the README, tag v0.1.0, publish to PyPI (check name availability), and post it somewhere. The project has been polished in private for 91 commits; the highest-value information now — does anyone else want this? — only comes from release. Even the outcome "nobody bites" is fine: as a personal tool it already pays rent, and as a portfolio piece it demonstrates config-system design, packaging, testing, and cross-platform GUI work.

**Worth it?** As a personal daily-driver and a learning/portfolio project: unambiguously yes, and it's close to being genuinely shareable. As a project hoping for wide adoption: possible but not likely in a crowded space — which is an argument for shipping the small sharp version soon, not for building the distributed vision first.

---

## Prioritized Recommendations

| # | Effort | Item |
|---|--------|------|
| 1 | ~half day | Rewrite README against the actual CLI (commands, `tasks:` key, remove corruption/placeholders, fix dead links) |
| 2 | small | Rename installed package `core` → `signalbox`; unblocks PyPI |
| 3 | small | Make PyQt6 an optional `[tray]` extra with lazy import |
| 4 | tiny | Fix log-dir lookup in `task run --all` / `group run` (`cli_commands.py:351,430`) |
| 5 | tiny | Align code fallback defaults with shipped `signalbox.yaml` (esp. `max_file_size_mb`) |
| 6 | tiny | Add GitHub Actions CI (tests run in 0.35s — there's no excuse not to) |
| 7 | small | Clean root-dir artifacts into `notes/` or delete |
| 8 | small | Per-task `timeout:` override (already on todo) |
| 9 | medium | Split `cli_commands.py` into per-group command modules; add public `ConfigManager.set_config_home()` |
| 10 | — | Tag v0.1.0 and publish; defer distributed features until there's a second user |
