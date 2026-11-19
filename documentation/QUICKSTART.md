# Quickstart: Monitor a Website and Your Disk

This tutorial takes about 15 minutes. At the end, you have:
- A website check and a disk check that run every 15 minutes
- A log of each run, and alerts when something is wrong
- The status in your menu bar (the tray) and in `signalbox status`

The commands are for macOS and Linux. Where the two systems are different, the tutorial tells you.

## 1. Install signalbox

Install pipx if you do not have it:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
```

Then install signalbox from your copy of the source, with the tray app:

```bash
cd /path/to/signalbox
pipx install ".[tray]"
signalbox --help
```

To change the signalbox code and use your changes immediately, install it with `pipx install --editable ".[tray]"`. To update an installation, add `--force`.

## 2. Try It in a Test Location

Before you change your real configuration, try signalbox in a temporary directory:

```bash
export SIGNALBOX_HOME=$(mktemp -d)
signalbox init
signalbox list
signalbox run hello
signalbox log show hello
unset SIGNALBOX_HOME
```

`SIGNALBOX_HOME` tells signalbox where its files are. When you remove the variable (`unset`), signalbox uses your real configuration again.

## 3. Make Your Configuration

```bash
signalbox init
signalbox config path
```

`signalbox init` makes `~/.config/signalbox/`. It has these items:
- `config/signalbox.yaml`: the global settings
- `config/tasks/` and `config/groups/`: your tasks and groups
- `logs/` and `runtime/`: the logs and the status of each run. Signalbox writes them.

The two example files (`config/tasks/example.yaml` and `config/groups/example.yaml`) have the tasks `hello` and `world`. You can delete them when you have your own tasks.

## 4. Write a Website Check

A task is a shell command. Signalbox records "success" when the command exits with 0, and "failed" for all other exit codes. Thus, a good check script exits with 1 when something is wrong.

Save this script as `~/.config/signalbox/scripts/check_site.sh`:

```sh
#!/bin/sh
# Check one website for signalbox.
# Usage: check_site.sh URL [TEXT]
# Exits 1 if the site does not answer with HTTP 2xx (after redirects), or if TEXT
# is given and the page does not contain it. For https, it also prints how many
# days the certificate is still valid, so an alert can warn before it expires.
url="$1"
text="$2"
[ -n "$url" ] || { echo "Usage: check_site.sh URL [TEXT]" >&2; exit 2; }

body=$(mktemp)
trap 'rm -f "$body"' EXIT

result=$(curl -sS -L -o "$body" -w '%{http_code} %{time_total}' --max-time 20 "$url")
if [ $? -ne 0 ]; then
    echo "DOWN: $url (no answer)"
    exit 1
fi
code=${result%% *}
seconds=${result##* }
echo "$url: HTTP $code in ${seconds}s"
case "$code" in
    2*) ;;
    *) echo "DOWN: $url answered HTTP $code"; exit 1 ;;
esac

if [ -n "$text" ] && ! grep -q "$text" "$body"; then
    echo "DOWN: $url does not contain \"$text\""
    exit 1
fi

case "$url" in
    https://*)
        host=$(echo "$url" | sed -E 's#^https://([^/:]+).*#\1#')
        end=$(echo | openssl s_client -servername "$host" -connect "$host:443" 2>/dev/null \
            | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
        if [ -n "$end" ]; then
            # macOS date first, then GNU date (Linux)
            end_s=$(date -j -f "%b %e %H:%M:%S %Y %Z" "$end" +%s 2>/dev/null || date -d "$end" +%s 2>/dev/null)
            [ -n "$end_s" ] && echo "Certificate valid for $(( (end_s - $(date +%s)) / 86400 )) more days"
        fi
        ;;
esac
exit 0
```

Make it executable, and try it:

```bash
chmod +x ~/.config/signalbox/scripts/check_site.sh
~/.config/signalbox/scripts/check_site.sh https://example.com "Example Domain"
echo $?    # 0 = the site is up
```

The text argument is optional. Use a word that is always on the page. Then signalbox also finds an error page that answers with HTTP 200.

## 5. Add the Tasks and a Group

Make the file `~/.config/signalbox/config/tasks/checks.yaml`:

```yaml
tasks:
  - name: site-example
    description: example.com is up and shows its title
    command: scripts/check_site.sh https://example.com "Example Domain"
    timeout: 60
    alerts:
      - pattern: "Certificate valid for ([0-9]|1[0-3]) more days"
        message: The certificate of example.com expires in less than 2 weeks
        severity: warning

  - name: disk-space
    description: Warn when the main disk is more than 90% full
    command: df -h / | tail -1
    timeout: 30
    alerts:
      - pattern: "(9[0-9]|100)%"
        message: The main disk is more than 90% full
        severity: critical
```

Commands run in the signalbox home. Thus, `scripts/check_site.sh` finds the script.

Only groups can have a schedule. Make the file `~/.config/signalbox/config/groups/checks.yaml`:

```yaml
groups:
  - name: checks
    description: Website and disk checks
    execution: parallel        # the tasks run at the same time
    schedule: "*/15 * * * *"   # every 15 minutes
    tasks: [site-example, disk-space]
```

To check more websites, add one task for each website, and add its name to the group. One task for each website tells you which website failed.

## 6. Validate and Run by Hand

```bash
signalbox validate
signalbox group run checks
signalbox list
signalbox log show site-example
```

`signalbox validate` finds errors before they stop a scheduled run, for example a missing field, an incorrect schedule, or a group that refers to a task that does not exist.

## 7. Schedule the Group

On macOS and Linux, use cron:

```bash
signalbox export-cron checks --install
crontab -l
```

`--install` adds the line to your crontab. Do the command again after you change the schedule: signalbox replaces its line and keeps your other cron jobs.

**macOS:** if a task reads Desktop, Documents, Downloads or an external drive, give cron access to them. Open System Settings > Privacy & Security > Full Disk Access. Click +, push Cmd+Shift+G, type `/usr/sbin/cron`, and turn it on. Without this access, the task fails with "Operation not permitted". The tasks in this tutorial do not need it.

**A laptop that sleeps:** cron does not run a job while the computer is asleep. To run missed groups soon after the computer wakes, add this to `~/.config/signalbox/config/signalbox.yaml`, and run `signalbox export-cron --all --install` again:

```yaml
scheduling:
  catch_up_minutes: 10
```

**Linux with systemd:** you can use a timer instead of cron:

```bash
signalbox export-systemd checks --user
```

The command shows how to install the timer.

## 8. Watch the Results

```bash
signalbox status
```

`signalbox status` shows each group and task, and exits with:
- 0: all is OK
- 1: a group did not run when it was due, the latest run of a task raised a warning alert, or a task skipped too many runs
- 2: something failed, or the latest run of a task raised a critical alert (for example, the disk check above)
- 3: there is no configuration yet

A `warning` alert gives exit code 1, and the tray turns yellow. Use a warning for results that need attention but are not broken, for example updates that are available. In the tray, **Mark all as seen** turns the icon green again until a later run raises a new alert.

To show the status in the menu bar, start the tray:

```bash
signalbox-tray &
```

The tray shows the signalbox box with one coloured tile: green when all is OK, yellow when a group is late or a task raised a warning, red when something failed. Click it to see each group and task. Click a task to open its latest log. To start the tray when you log in, refer to [TRAY_USAGE.md](TRAY_USAGE.md#autostart).

To test desktop notifications:

```bash
signalbox notify-test
```

**macOS:** if no notification shows, open System Settings > Notifications, and turn on notifications for **Script Editor**. Signalbox sends notifications with `osascript`, and macOS shows them as notifications from Script Editor.

## 9. Every Day

| To do this | Use this command |
|------------|------------------|
| See if all is OK | `signalbox status` (or look at the tray) |
| See the latest runs | `signalbox log list --last 20` |
| See only failures | `signalbox log list --failed` |
| See the output of a run | `signalbox log show TASK` |
| See the alerts | `signalbox alerts` |
| Follow a task while it runs | `signalbox log tail TASK` |
| Run a check now | `signalbox group run checks` |

## 10. Next Steps

- **Skip instead of fail.** Use `run_if` when a task needs something that is not always there, for example an external drive: `run_if: test -d /Volumes/Backup`. Signalbox then skips the task, and does not show it as a failure.
- **Secrets.** Put tokens and passwords in an `env_file` (`chmod 600`), not in the command. Refer to [SECURITY.md](SECURITY.md).
- **Different computers.** Use `platforms: [darwin]` or `platforms: [linux]` to share one configuration between computers.
- **More settings.** Refer to [CONFIG_GUIDE.md](CONFIG_GUIDE.md), [FILE_STRUCTURE.md](FILE_STRUCTURE.md) and [WRITING_SCRIPTS.md](WRITING_SCRIPTS.md).

## If Something Does Not Work

1. Run `signalbox validate`.
2. Run the group by hand (`signalbox group run checks`). Compare the result with the scheduled run.
3. Look at `signalbox log list --failed` and `signalbox log show TASK`.
4. Make sure that cron has the line: `crontab -l`.
