# 1. The computer and syncing

The assistant lives on one computer that's always on. In this chapter you get that machine ready: Python, Claude Code logged in to your subscription, and your vault synced to it.

## Which computer

Anything running Linux that you can leave on. I'd go for an old laptop. It's quiet, it barely uses any power, and when the power goes out for a few minutes the battery just takes over. The assistant itself needs almost nothing, because Claude runs in the cloud and the laptop only passes messages along and reads files.

I'm using Fedora in the commands below. On Ubuntu or Debian, swap `dnf` for `apt` and the rest is identical.

## Basics

```bash
sudo dnf install -y python3 git syncthing    # Ubuntu/Debian: sudo apt install python3 python3-venv git syncthing
python3 --version                            # needs 3.10 or newer
```

## Claude Code

The bot talks to Claude through the Claude Code CLI, logged in with your Pro or Max account.

```bash
curl -fsSL https://claude.ai/install.sh | bash
claude              # first run: log in with your Claude account, then type /exit
claude -p "reply with just: ok"
```

If the last line prints `ok`, you're good. Check where it ended up with `which claude` (normally `~/.local/bin`); the installer later needs that folder.

Make sure `ANTHROPIC_API_KEY` isn't set anywhere. If it is, Claude Code bills API credits instead of using your subscription. Run `env | grep ANTHROPIC_API_KEY` and look through `~/.bashrc`, `~/.bash_profile` and `~/.profile` too. The bot won't start if it finds the variable, so you'd notice, but it's better to sort it now.

## Syncthing

The notes are plain files on this computer, and Syncthing keeps them in sync with your phone and your other machines directly, device to device.

Run it as a systemd service:

```bash
systemctl --user enable --now syncthing
loginctl enable-linger "$USER"     # start user services at boot, even before anyone logs in
systemctl --user is-active syncthing
```

Don't start it from your desktop's app menu as well. I did that by accident and ended up with two copies fighting over the same lock: the service kept failing with "Failed to acquire lock: is another Syncthing instance already running?", and the copy that did run only lived as long as I was logged in. If you see that error in `systemctl --user status syncthing`, close the menu-started one and restart the service.

### Sharing the vault

Open the web UI at <http://127.0.0.1:8384>. If your vault already exists on another device, add that device and accept the folder it shares. If you're starting fresh, just create a folder, e.g. `~/Documents/ObsidianVault`. On the phone I use Synctrain (iOS); on Android, Syncthing-Fork does the same job. Point the Obsidian app at the synced folder.

Wait until Syncthing says "Up to Date" before you carry on.

### Leave Obsidian's window layout out of it

Every time you switch tabs, Obsidian rewrites `.obsidian/workspace.json`. Have the vault open on two devices and you'll get a steady stream of `.sync-conflict-` files out of that alone. Put a file called `.stignore` in the vault root with:

```
// Obsidian window layout: each device keeps its own
.obsidian/workspace.json
.obsidian/workspace-mobile.json
```

`.stignore` doesn't sync itself, so add the same two lines on every device (in Synctrain or Syncthing-Fork they're under the folder's ignore patterns).

### File versioning

In the web UI: open the folder, Edit, File Versioning, pick Staggered with a maximum age of 90 days. From then on Syncthing keeps old copies of files that another device changed or deleted.

That only covers changes that *come in* from other devices, though. Whatever gets changed on this computer, which is where the assistant writes, isn't versioned by Syncthing. The hourly snapshot in [chapter 7](07-always-on.md) takes care of that.

## Before moving on

- [ ] `python3 --version` is 3.10 or newer
- [ ] `claude -p "reply with just: ok"` prints `ok`
- [ ] `ANTHROPIC_API_KEY` isn't set anywhere
- [ ] `systemctl --user is-active syncthing` says `active` and linger is on
- [ ] the vault is on this computer, up to date, with a `.obsidian/` folder in it

On to [the Discord bot](02-discord-bot.md).
