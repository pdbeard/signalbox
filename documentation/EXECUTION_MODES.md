# Parallel and Serial Execution Guide

## Overview

Signalbox can run the tasks of a group in two modes:

- **Serial**: the tasks run one at a time, in the sequence of the list.
- **Parallel**: the tasks run at the same time. Thus, the group finishes faster.

## Serial Execution

### When to Use

Use serial execution in these conditions:
- A task uses the result of a different task.
- The sequence of the tasks is important.
- The tasks use the same resources, for example files or databases.
- You must know the sequence in which the tasks run.

### Configuration

```yaml
groups:
  - name: deployment
    description: Deploy application
    execution: serial  # One task at a time
    tasks:
      - pre_deploy_check
      - build_app
      - deploy_app
      - post_deploy_test
```

### Stop on Error

For important workflows, you can stop the group when a task fails:

```yaml
groups:
  - name: deployment
    description: Deploy application
    execution: serial
    stop_on_error: true  # Stop when a task fails
    tasks:
      - pre_deploy_check  # If this task fails, the group stops here
      - build_app         # This task runs only if the tasks before it were successful
      - deploy_app
      - post_deploy_test
```

With `stop_on_error: false` (the default), a failed task does not stop the group. Signalbox runs all the tasks.

With `stop_on_error: true`, signalbox stops at the first failed task. This is the output (shorter log paths):
```
Running group deployment: Deploy application
Execution mode: serial (stop_on_error: True)

Running pre_deploy_check...
Task pre_deploy_check success. Log: ~/.config/signalbox/logs/pre_deploy_check/20261117_143312_556447.log

Running build_app...
Task build_app failed. Log: ~/.config/signalbox/logs/build_app/20261117_143312_562623.log
Task build_app failed. The remaining tasks do not run (stop_on_error: true)
```

Then a table shows each task. The tasks that did not run have the status `skipped`.

### Group Result

After each run, signalbox records the status of the group:
- `success`: all tasks were successful.
- `partial`: some tasks were successful, and some failed or did not run.
- `failed`: no task was successful.
- `skipped`: signalbox skipped all the tasks on purpose (`run_if`, `overlap` or `platforms`).

A task that signalbox skips on purpose does not count for or against the group, and it does not stop a group with `stop_on_error: true`. A task that `stop_on_error` stops does count: an earlier task failed.

If the status is not `success` or `skipped`, `signalbox group run` exits with code 1. Thus, cron and systemd see the failure.

## Parallel Execution

### When to Use

Use parallel execution in these conditions:
- The tasks do not use the results of other tasks.
- Speed is important.
- The tasks do not change the same resources.
- The tasks monitor different systems or services.

### Configuration

```yaml
groups:
  - name: monitoring
    description: Check all services
    execution: parallel  # All tasks at the same time
    tasks:
      - check_web_server
      - check_database
      - check_cache
      - check_queue
```

### Stop a Parallel Group

If you push Ctrl+C, signalbox stops all the tasks of the group that are running. The tasks that did not start, do not start.

### Execution Summary

After a parallel run, signalbox shows a summary:

```
Parallel execution summary:
  Completed: 4/4
  Successful: 3/4
  Failed: check_database
```

## Configuration Settings

### Global Config (signalbox.yaml)

This setting controls the maximum number of tasks that run at the same time:

```yaml
execution:
  max_parallel_workers: 5  # Max tasks running at once
```

- **Higher values** (10 to 20): more tasks at the same time. The group is faster, but it uses more resources.
- **Lower values** (3 to 5): fewer tasks at the same time. The group is slower, but it uses fewer resources.
- **Default**: 5 workers

## Example
You can use the two modes in different groups:

```yaml
groups:
  # Fast parallel monitoring
  - name: health_checks
    description: Health checks of all services
    execution: parallel
    schedule: "* * * * *"  # Every minute
    tasks:
      - check_api_health
      - check_db_health
      - check_cache_health

  # Critical serial deployment
  - name: deploy_api
    description: Test, build and deploy the API
    execution: serial
    stop_on_error: true
    tasks:
      - run_api_tests
      - build_api
      - deploy_api
      - verify_api

  # Parallel data collection
  - name: metrics_collection
    description: Collect system metrics
    execution: parallel
    schedule: "*/10 * * * *"  # Every 10 minutes
    tasks:
      - collect_cpu_metrics
      - collect_memory_metrics
      - collect_disk_metrics
      - collect_network_metrics
```

