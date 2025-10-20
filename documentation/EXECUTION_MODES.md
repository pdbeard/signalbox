# Parallel and Serial Execution Guide

This guide explains how to use parallel and serial execution modes in script-monitor.

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

### Performance Example

**Serial execution:**
```
check_web_server   (10s) ─────────────>
check_database              (10s) ─────────────>
check_cache                          (10s) ─────────────>
check_queue                                   (10s) ─────────────>
Total time: 40 seconds
```

**Parallel execution:**
```
check_web_server   (10s) ─────────────>
check_database     (10s) ─────────────>
check_cache        (10s) ─────────────>
check_queue        (10s) ─────────────>
Total time: ~10 seconds
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

### Global Config (config.yaml)

Control maximum concurrent scripts:

```yaml
execution:
  max_parallel_workers: 5  # Max scripts running at once
```

- **Higher values** (10-20): More concurrent scripts, faster but more resource-intensive
- **Lower values** (3-5): Fewer concurrent scripts, slower but more controlled
- **Default**: 5 workers

## Real-World Examples

### Example 1: System Monitoring (Parallel)

Monitor multiple systems quickly:

```yaml
groups:
  - name: infrastructure_check
    description: Check all infrastructure
    execution: parallel
    schedule: "*/5 * * * *"  # Every 5 minutes
    scripts:
      - check_web_server_1
      - check_web_server_2
      - check_database_primary
      - check_database_replica
      - check_redis_cache
      - check_message_queue
      - check_storage_server
```

**Benefits:**
- 7 scripts complete in ~10 seconds instead of 70 seconds
- More frequent monitoring possible
- Faster alerting on issues

### Example 2: Deployment Pipeline (Serial + Stop on Error)

Deploy application safely:

```yaml
groups:
  - name: production_deploy
    description: Deploy to production
    execution: serial
    stop_on_error: true  # Critical: stop on any failure
    scripts:
      - run_tests           # Must pass
      - backup_database     # Must succeed before deploy
      - stop_application    # Must stop cleanly
      - deploy_new_version  # Only if previous steps passed
      - run_migrations      # Only if deploy succeeded
      - start_application   # Only if migrations passed
      - smoke_tests         # Verify deployment
      - notify_team         # Send success notification
```

**Safety:**
- If tests fail, nothing else runs
- If backup fails, deploy is skipped
- If deploy fails, migrations don't run
- Each step validates the previous step succeeded

### Example 3: Data Processing (Serial, Continue on Error)

Process multiple data sources, even if some fail:

```yaml
groups:
  - name: data_import
    description: Import from all sources
    execution: serial
    stop_on_error: false  # Continue even if some sources fail
    scripts:
      - import_from_source_a
      - import_from_source_b
      - import_from_source_c
      - import_from_source_d
      - generate_report  # Runs even if some imports failed
```

**Benefits:**
- Partial data is better than no data
- Report shows which sources succeeded
- Don't block on one failing source

### Example 4: Mixed Approach

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

## Best Practices

### Parallel Execution

✅ **Do:**
- Use for independent scripts
- Use for monitoring/health checks
- Set appropriate `max_parallel_workers`
- Consider system resources

❌ **Don't:**
- Use for dependent scripts
- Use for scripts that modify the same files
- Set `max_parallel_workers` too high
- Use for critical sequential workflows

### Serial Execution

✅ **Do:**
- Use `stop_on_error: true` for critical workflows
- Use for deployment pipelines
- Use when order matters
- Use for scripts that share resources

❌ **Don't:**
- Use when scripts are independent (use parallel instead)
- Forget to set `stop_on_error` for critical workflows
- Make groups too large (split into smaller groups)

## Troubleshooting

### Parallel Execution Issues

**Problem:** Scripts fail intermittently in parallel mode
- **Cause:** Race conditions or shared resource conflicts
- **Solution:** Switch to serial mode or fix resource conflicts

**Problem:** Parallel execution is slow
- **Cause:** `max_parallel_workers` set too low
- **Solution:** Increase `max_parallel_workers` in config.yaml

**Problem:** System runs out of resources
- **Cause:** Too many concurrent scripts
- **Solution:** Decrease `max_parallel_workers`

### Serial Execution Issues

**Problem:** Group takes too long to execute
- **Cause:** Running too many scripts serially
- **Solution:** Split into smaller groups or use parallel mode for independent scripts

**Problem:** One script failure stops everything
- **Cause:** `stop_on_error: true`
- **Solution:** Set `stop_on_error: false` if you want to continue

## Command Reference

### Run a Group

```bash
# Run with configured execution mode
python main.py run-group <group_name>
```

The execution mode is configured in `groups.yaml`, not specified at runtime.

### List Groups

See execution mode for each group:

```bash
python main.py list-groups
```

Output shows execution mode:
```
Group: monitoring [execution: parallel]
Group: deployment [execution: serial, stop_on_error]
```

### View Configuration

```bash
# See max_parallel_workers setting
python main.py get-setting execution.max_parallel_workers
```

## Migration from Old Config

If you have existing groups without `execution` specified:

**Default behavior:**
- Groups without `execution` field run in **serial** mode
- `stop_on_error` defaults to **false** (continue on error)

**To add parallel execution:**

```yaml
# Old (implicit serial)
groups:
  - name: monitoring
    scripts:
      - check_service_1
      - check_service_2

# New (explicit parallel)
groups:
  - name: monitoring
    execution: parallel  # Add this line
    scripts:
      - check_service_1
      - check_service_2
```

**To add stop-on-error:**

```yaml
# Old (continues on error)
groups:
  - name: deployment
    scripts:
      - build
      - deploy

# New (stops on error)
groups:
  - name: deployment
    execution: serial      # Add this line
    stop_on_error: true    # Add this line
    scripts:
      - build
      - deploy
```

## Summary

| Feature | Serial | Parallel |
|---------|--------|----------|
| **Execution** | One at a time | Simultaneous |
| **Speed** | Slower | Faster |
| **Order** | Guaranteed | Not guaranteed |
| **stop_on_error** | ✓ Supported | ✗ Not applicable |
| **Best for** | Dependent scripts | Independent scripts |
| **Use case** | Deployments | Monitoring |

Choose the right execution mode for each group based on your requirements!
