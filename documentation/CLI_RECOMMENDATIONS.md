# CLI Review & Recommendations for Signalbox

Purpose
- Concise review of the existing CLI (`core/cli_commands.py`) and prioritized recommendations for fixes, improvements, and new commands. No code changes included — this is a specification you can review first.

Summary
- The CLI is well-structured using Click with clear commands and a central exception handler. Major opportunities: terminology consistency (scripts → tasks), a few missing backward-compatible aliases, clearer exit codes for batch operations, improved `init()` XDG handling, and some useful UX/automation commands.

High-level issues
- Inconsistent terminology: user-facing text, some helper names, and tests vary between `script(s)` and `task(s)`.
- Backwards-compatibility: tests/docs reference `history` while CLI exposes `log-history` (aliasing needed).
- `init()` hardcodes `~/.config/signalbox` and uses local package lookup; should respect `XDG_CONFIG_HOME` and provide clearer guidance when templates are missing.
- `run_all()` silently continues on task errors without returning a non-zero exit code; hard for CI to detect failures.
- Some log-manager and runtime function names (e.g., `get_task_log_dir` vs `get_script_log_dir`) are inconsistent across modules and tests.
- `handle_exceptions()` assumes SignalboxError subclasses expose `.message` and `.exit_code` — ensure all subclasses comply.

Short-term (low-risk) recommendations
1. Terminology cleanup (user-visible only): replace remaining "script(s)" strings in `cli_commands.py` and messages with `task(s)`. This avoids user confusion without structural changes.
2. Add small aliases for compatibility:
   - `history` → alias to `log-history`
   - Keep a `run` alias (if tests/docs expect a different name) — ensure tests map to final names.
3. Make `run_all()` exit non-zero when any task fails (e.g., `sys.exit(2)`), or add `--exit-on-error` flag. This is critical for CI/doctl use.
4. Ensure `handle_exceptions()` prints meaningful messages if `.message` or `.exit_code` missing (fallback to str(e) and exit code 1).

Medium-term (medium risk / medium effort)
1. Standardize internal API naming: pick either `task_*` or `script_*` for log/runtime/export functions and update modules + tests. Prefer `task_*` if the repo migrated to `tasks` concept.
2. Improve `init()` to respect XDG and accept `--dest` flag; when templates not found, suggest commands for reinstall or a `--create-minimal` fallback.
3. Add global verbosity flags: `--quiet` and `--verbose` for `cli()` to control click.echo output and logging levels.
4. Enhance `run-group`:
   - Add flags: `--parallel/--serial` to override group config, `--max-workers` for parallel, `--no-save-runtime` to skip persisting runtime state.
5. Add `--dry-run` to `run`/`run_all` to validate execution plan without running tasks.

Long-term (new features / higher effort)
1. Notifications management subcommands: `notifications show`, `notifications enable`, `notifications disable`, `notifications set` (e.g., set `alerts.notifications.on_failure_only`).
2. Task lifecycle commands: `task enable|disable <name>` (persist disable in runtime or suggest config edits), `task status [<name>]` (show last_status, last_run, next scheduled run if in a group).
3. Add `task history <name> --tail N` alias to quickly tail task logs or integrate with `less`/`tail -f`.
4. Add `run --parallel <list>` helper that accepts multiple task names and runs them with configurable concurrency.
5. Add `export` command group that consolidates `export-systemd` and `export-cron` with a unified interface `export systemd|cron <group>`.

Suggested new commands (brief)
- `history` (alias to `log-history`) — compatibility convenience.
- `notifications show|enable|disable` — manage notification defaults from CLI.
- `task status [name]` — single place to read runtime state for a task.
- `task disable <name>` — optional: marks a task disabled in runtime (skips in `run_all`) or prints a config patch suggestion.
- `run --dry-run` — print what would run without executing.

CLI ergonomics & UX
- Add global `--config` doc string on `init()` and show where user config is expected.
- Improve messages in `init()` to use `XDG_CONFIG_HOME` and to explicitly mention `pipx`/`pip install .` if templates are missing.
- Return meaningful exit codes: 0 (success), 2 (task run failures), 3 (usage/config errors), 5 (validation errors) — document these in README.
- Add machine-readable flags (e.g., `--json` output for `list`, `status`) to ease automation.

Compatibility / Migration notes
- If you standardize on `tasks`, update all tests and helpers to match. Alternatively, keep internal names as `scripts` but ensure user-facing strings use `task` for clarity — pick one to avoid repeated churn.
- When adding aliases (e.g., `history`), keep them for at least one major release to avoid breaking users.

Testing & Validation
- Add unit tests for new flags and aliases.
- Add CI job that runs `run_all --dry-run` and validates exit codes when tasks fail.
- Expand integration tests for `init()` across typical environments (no XDG, with XDG, packaged install).

Next steps (pick one)
- I can prepare a minimal PR that:
  - Adds `history` alias for `log-history` and replaces remaining user-visible "scripts" → "tasks" strings in `cli_commands.py` (low-risk), or
  - Draft a full standardization plan (all function names, tests, docs) and an implementation branch (higher risk). 

If you want the doc edited or expanded (e.g., more examples, exact CLI prototypes, or proposed exit code table), tell me which section to expand.

File created: `documentation/CLI_RECOMMENDATIONS.md` — review and tell me which items to implement first.