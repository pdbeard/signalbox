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
    execution: serial  # Run one at a time
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
    stop_on_error: true  # Stop if any task fails
    tasks:
      - pre_deploy_check  # If this fails, stop here
      - build_app         # Won't run if previous failed
      - deploy_app
      - post_deploy_test
```

**With `stop_on_error: false` (default):**
```
Running deployment...
Running pre_deploy_check... ✓
Running build_app... ✗ FAILED
Running deploy_app... ✓ (still runs)
Running post_deploy_test... ✓ (still runs)
```

**With `stop_on_error: true`:**
```
Running deployment...
Running pre_deploy_check... ✓
Running build_app... ✗ FAILED
⚠️  Task build_app failed. Stopping group execution (stop_on_error=true)
(deploy_app and post_deploy_test do not run)
```

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
    execution: parallel  # Run simultaneously
    tasks:
      - check_web_server
      - check_database
      - check_cache
      - check_queue
```

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
    execution: parallel
    schedule: "* * * * *"  # Every minute
    tasks:
      - check_api_health
      - check_db_health
      - check_cache_health

  # Critical serial deployment
  - name: deploy_api
    execution: serial
    stop_on_error: true
    tasks:
      - run_api_tests
      - build_api
      - deploy_api
      - verify_api

  # Parallel data collection
  - name: metrics_collection
    execution: parallel
    schedule: "*/10 * * * *"  # Every 10 minutes
    tasks:
      - collect_cpu_metrics
      - collect_memory_metrics
      - collect_disk_metrics
      - collect_network_metrics
```

