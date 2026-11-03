# 7. Running it 24/7

The bot and Syncthing already start at boot without anyone logging in, thanks to linger and the systemd user services. What's left is keeping the computer from going to sleep, looking after the battery if it's a laptop, and backups.

## No sleeping

```bash
sudo bash ~/agent/always-on.sh
```

The script masks every sleep target (`sleep`, `suspend`, `hibernate`, `hybrid-sleep`, `suspend-then-hibernate`), so nothing can put the machine to sleep: not the desktop's idle timer, not the lid, not the menu. It also tells `logind` to ignore the lid, so you can close it and leave it on a shelf. The screen still turns off by itself.

On laptops whose battery supports charge thresholds (ThinkPads and plenty of others), it also limits charging to between 75% and 80%. A battery sitting at 100% all the time wears out fast, and 80% is still plenty to get through a short power cut. On a desktop that part is skipped. The commands to undo all of it are at the top of the script.

If your BIOS has a setting for powering on when AC comes back (often called "Power On with AC Attach" or "Restore on AC Power Loss"), turn it on. After a power cut longer than the battery lasts, the computer then boots by itself and the services come up without a login.

## Backups

`install.sh` already turned on `agent-snapshot.timer`. Once an hour, `vault-snapshot.sh` commits the whole vault into a git repo outside the vault, at `~/vault-history`, so nothing extra gets synced around. It leaves out `Private/`, sync-conflict files and Obsidian's window layout. It only commits when something changed, and unchanged notes are stored once, so it stays tiny; mine is a few hundred KB.

To get an old version of a note back:

```bash
H="git --git-dir=$HOME/vault-history --work-tree=$HOME/Documents/ObsidianVault"
$H log --oneline -- "Ideas/app ideas.md"       # snapshots where this note changed
$H checkout <commit> -- "Ideas/app ideas.md"   # put that version back
```

Between this and Syncthing's file versioning from chapter 1, you're covered from both sides. Changes made on this computer, by you or by the assistant, are in the hourly snapshots. Changes coming from your phone or another computer are in the snapshots too, and also in Syncthing's `.stversions/`.

None of that helps if the laptop itself dies or gets stolen, so if the vault matters to you, keep an offsite copy of `~/vault-history` and `~/agent/.env` as well, on an encrypted USB stick or with whatever backup tool you already use.

## Keeping it up to date

Claude Code may be set to not update itself. Every month or two, run `claude update` and then `systemctl --user restart agent`. After pulling new code for the bot, run `bash install.sh && systemctl --user restart agent`.

If your Claude login ever expires, the bot replies with a ⚠️ error. Run `claude` on the computer, log in again, and it's back.

## Moving to another computer

Only one computer can run the bot at a time. If two do, you get every answer twice. I found that out the hard way during testing.

Set up the new machine as in chapter 1 and wait until the vault has finished syncing. Copy the code over and run `bash install.sh`. Bring `~/agent/.env` over some private way, like a USB stick or `scp`, never through the vault or git, and fix `VAULT_PATH` if the vault lives somewhere else now.

If you want to keep your history, copy `~/vault-history` as well. Old conversations can come along too: copy `~/agent/state/` and Claude's transcripts in `~/.claude/projects/<vault path with / replaced by ->/`. That only works if the vault has the same path on the new machine. If you skip it, old threads just start fresh, which the bot copes with on its own.

Then switch:

```bash
(old)  systemctl --user disable --now agent agent-snapshot.timer
(new)  systemctl --user restart agent
```

And run `sudo bash ~/agent/always-on.sh` on the new one if it should stay on. Nothing needs to change on the Discord side; the same token works from any computer.

Next: [things that went wrong](08-gotchas.md).
