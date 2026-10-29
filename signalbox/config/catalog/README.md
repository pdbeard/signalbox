# Signalbox Catalog

The catalog has tasks and groups that are ready to use. Signalbox does not load
the catalog by default. To use it, do one of these steps:

- Copy the files that you want into your `tasks/` and `groups/` directories.
- Set `include_catalog: true` in `signalbox.yaml` to load all of the catalog.

**Caution:** if you set `include_catalog: true`, `task run --all` also runs all
catalog tasks.

---

## Tasks

### system_health.yaml
| Task | Purpose | Edit before use? |
|------|---------|-----------------|
| `check_disk_space` | Disk usage across real filesystems; excludes snap/squashfs on Linux | No |
| `check_memory_pressure` | Memory pressure (macOS `memory_pressure` or Linux `free -m`) | No |
| `check_system_load` | Load averages vs CPU count; alerts when 5-min load exceeds core count | No |

### web_monitoring.yaml
| Task | Purpose | Edit before use? |
|------|---------|-----------------|
| `check_website_health` | HTTP status + response time (single request) | **Yes** — set `URL` |
| `check_ssl_expiry` | SSL cert expiry: warning at 30 days, critical at 7 | **Yes** — set `HOST` |
| `check_dns_resolution` | DNS lookup via `dig`, falls back to `host` | **Yes** — set `DOMAIN` |
| `ping_connectivity` | Outbound connectivity via ICMP ping to 8.8.8.8 | No |

### maintenance.yaml
| Task | Purpose | Edit before use? |
|------|---------|-----------------|
| `clean_old_tmp_files` | Removes files (not dirs) from `/tmp` older than 7 days | No |
| `check_large_files` | Finds files >1 GB in `~` (5 levels deep, skips hidden) | No |
| `verify_recent_backup` | Checks for a recent archive in `~/backups` | **Yes** — set `BACKUP_DIR` |

### dev_tools.yaml
| Task | Purpose | Edit before use? |
|------|---------|-----------------|
| `dirty_repos` | Scans `~/development` for repos with uncommitted/unpushed changes | **Yes** — set `DEV_DIR` |
| `process_watchdog` | Alerts if a named process is not running | **Yes** — set `PROCESS_NAME` |
| `port_check` | Checks that a local service is listening on a port | **Yes** — set `HOST`, `PORT`, `SERVICE` |
| `check_updates` | Reports pending updates via `brew` or `apt` | No |
| `scan_log_errors` | Scans last N lines of a log file for ERROR/CRITICAL | **Yes** — set `LOG_FILE` |
| `signalbox_selfcheck` | Runs `signalbox validate`; turns tray red on config errors | No |

### alerts_test.yaml / test.yaml
Demonstration tasks that show alert patterns and error handling. Do not use them in production.

---

## Groups

### system_health.yaml
| Group | Tasks | Schedule |
|-------|-------|----------|
| `system_health_check` | disk + memory + load | every 15 min |
| `daily_maintenance` | tmp cleanup + large files + backup check | 2am daily |

### web_monitoring.yaml
| Group | Tasks | Schedule |
|-------|-------|----------|
| `web_health_check` | website + SSL + DNS + ping | every 10 min |

### weekly.yaml
| Group | Tasks | Schedule |
|-------|-------|----------|
| `weekly_report` | large files + updates + dirty repos | Sunday 9am |

### monitoring.yaml
| Group | Tasks | Schedule |
|-------|-------|----------|
| `comprehensive_monitoring` | all system + network tasks | **none** — reference only |

### test.yaml
Demonstration groups that show how `stop_on_error` works. Do not use them in production.

---

## Notes

- The tables above show the tasks that you must edit before use. If you run them
  with the `example.com` or `~/backups` placeholders, they do no damage. But their
  results are not useful.
- `check_memory_pressure`, `check_disk_space`, `check_dns_resolution` and
  `check_updates` work on macOS and Linux without changes.
- The `weekly_report` group uses the tasks in `maintenance.yaml` and in
  `dev_tools.yaml`.
