# Parallel and Serial Execution Guide

## Overview

Script-monitor supports two execution modes for groups:

- **Serial** - Scripts run one at a time in order
- **Parallel** - Scripts run simultaneously for faster execution

## Serial Execution

### When to Use

Use serial execution when:
- Scripts depend on each other
- Execution order matters
- Scripts share resources (files, databases, etc.)
- You need predictable, sequential execution

### Configuration

```yaml
groups:
  - name: deployment
    description: Deploy application
    execution: serial  # Run one at a time
    scripts:
      - pre_deploy_check
      - build_app
      - deploy_app
      - post_deploy_test
```

### Stop on Error

For critical workflows, you can stop execution if any script fails:

```yaml
groups:
  - name: deployment
    description: Deploy application
    execution: serial
    stop_on_error: true  # Stop if any script fails
    scripts:
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
⚠️  Script build_app failed. Stopping group execution
(deploy_app and post_deploy_test are skipped)
```

## Parallel Execution

### When to Use

Use parallel execution when:
- Scripts are independent
- Speed is important
- Scripts don't modify shared resources
- Monitoring multiple systems/services

### Configuration

```yaml
groups:
  - name: monitoring
    description: Check all services
    execution: parallel  # Run simultaneously
    scripts:
      - check_web_server
      - check_database
      - check_cache
      - check_queue
```

### Execution Summary

Parallel execution shows a summary at the end:

```
Parallel execution summary:
  Completed: 4/4
  Successful: 3/4
  Failed: check_database
```

## Configuration Settings

### Global Config (signalbox.yaml)

Control maximum concurrent scripts:

```yaml
execution:
  max_parallel_workers: 5  # Max scripts running at once
```

- **Higher values** (10-20): More concurrent scripts, faster but more resource-intensive
- **Lower values** (3-5): Fewer concurrent scripts, slower but more controlled
- **Default**: 5 workers

## Example
Use both modes for different groups:

```yaml
groups:
  # Fast parallel monitoring
  - name: health_checks
    execution: parallel
    schedule: "* * * * *"  # Every minute
    scripts:
      - check_api_health
      - check_db_health
      - check_cache_health

  # Critical serial deployment
  - name: deploy_api
    execution: serial
    stop_on_error: true
    scripts:
      - run_api_tests
      - build_api
      - deploy_api
      - verify_api

  # Parallel data collection
  - name: metrics_collection
    execution: parallel
    schedule: "*/10 * * * *"  # Every 10 minutes
    scripts:
      - collect_cpu_metrics
      - collect_memory_metrics
      - collect_disk_metrics
      - collect_network_metrics
```

