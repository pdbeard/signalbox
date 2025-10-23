# Configuration File Structure

This document explains the directory-based configuration system for signalbox.

## File Structure Overview

```
signalbox/
├── scripts/           # Script definitions directory
│   ├── *.yaml         # Any and all script definition files
├── groups/            # Group definitions directory
│   ├── *.yaml         # Any and all group definition files
├── signalbox.yaml     # Global configuration
├── main.py            # CLI application
└── logs/              # Execution logs
```

## Configuration System

signalbox uses **directory-based configuration** for easy organization:

### **Scripts Directory** (`scripts/`)
Contains YAML files defining scripts to execute.
 - All `.yaml` and `.yml` files in the directory are loaded (sorted alphabetically)
 - Scripts from all files are combined into a single list

### **Groups Directory** (`groups/`)
Contains YAML files defining groups of scripts and scheduling. 
- All `.yaml` and `.yml` files in the directory are loaded (sorted alphabetically)
- Groups from all files are combined into a single list

### **Global Config** (`signalbox.yaml`)
Single file containing global settings like timeouts, log limits, and paths.

## Scripts Directory Configuration

### Script Format

**Fields:**
- `name` (required) - Unique identifier
- `description` (required) - Human-readable description
- `command` (required) - Shell command to execute
- `log_limit` (optional) - Log rotation configuration
- `last_run` (auto) - Last execution timestamp
- `last_status` (auto) - Last execution status

**Note:** Field order in YAML doesn't affect functionality.

## Groups Directory Configuration

**Fields:**
- `name` (required) - Unique identifier
- `description` (required) - Purpose of the group
- `scripts` (required) - List of script names
- `schedule` (optional) - Cron expression for automation
- `execution` (optional) - Execution mode: `serial` (default) or `parallel`
- `stop_on_error` (optional) - For serial execution only: stop if a script fails (default: false)

