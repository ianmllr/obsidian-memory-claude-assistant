# 4. Install and first run

If you're letting Claude Code set things up ([the quick way](../README.md#the-quick-way-let-claude-code-do-it)), it does this chapter for you. You only have to paste the token into `.env` and run the Discord tests at the end.

## Get the code

```bash
git clone https://github.com/ianmllr/obsidian-memory-claude-assistant.git ~/assistant-guide
cp -r ~/assistant-guide/assistant ~/agent
cd ~/agent
```

I keep the program in `~/agent` and the rest of the guide assumes that, but any folder works, since `install.sh` uses whatever path it's run from. It's worth running `git init` in there so you can see and undo your own changes later. `.env` is already in `.gitignore`; keep it that way.

## Run the installer

```bash
bash install.sh
```

It first checks that Python is new enough, that you're logged in to Claude and that `ANTHROPIC_API_KEY` isn't set. Then it makes a virtual environment with the dependencies (`claude-agent-sdk`, `discord.py`, `python-dotenv`, `caldav`), creates `.env` from `.env.example` with permissions `600`, installs two systemd user services (the bot and the hourly vault snapshot) with the right paths and `claude` on their `PATH`, and turns on linger so all of it starts at boot.

It doesn't start the bot. You can run it again any time, e.g. after updating the code.

## Fill in `.env`

Open `~/agent/.env` in an editor. It's a hidden file, so in a file manager press Ctrl+H to see it.

```ini
DISCORD_TOKEN=paste-bot-token-here      ← the bot token from chapter 2
OWNER_ID=123456789012345678             ← your Discord user ID
VAULT_PATH=~/Documents/ObsidianVault    ← your vault
```

Leave the rest for now; the heartbeat settings are in [chapter 6](06-heartbeat.md). And don't ever move `.env` into the vault, or your token gets synced to every device you own.

## Start it

```bash
systemctl --user restart agent
journalctl --user -u agent -f        # live log, Ctrl+C to stop watching
```

After a few seconds you should see something like:

```
Heartbeat: calendar off (no ICLOUD_* in .env), mail off (no GMAIL_* in .env)
... discord.gateway: Shard ID None has connected to Gateway ...
Logged in as YourBot#1234. Vault: /home/you/Documents/ObsidianVault
```

If it dies with `PrivilegedIntentsRequired`, Message Content Intent isn't on yet (chapter 2).

## Try it out

These are the things I tested mine with. Each one exercises a different part.

1. In `#chat`: "what do you know about me?" You should get a thread, and an answer based on `about-me.md`.
2. In that thread: "what did I just ask you?" It should know.
3. In `#quick`: "remind me to renew the domain on Friday". One line back, followed by `📥 Saved to Agent/daily/…: - [ ] Renew the domain 📅 … #todo`.
4. In `#quick`: "idea: a dark mode for my site". Saved with `#idea`, linked to a related note if there is one.
5. In `#chat`: "what do I have to do?" It should list the reminder from step 3.
6. In `#chat`: "my laptop has 32 GB RAM". You should get a proposed change to `Devices.md` with Approve and Reject buttons. Approve it and look at the note.
7. In `#chat`, attach a screenshot and ask what's in it.
8. In `#chat`: "help me plan a birthday party, make a note for it with a checklist". You should get `🆕 Created Home/…` and a new note with tags and a checklist.

Then restart the bot (`systemctl --user restart agent`) and reply in the first thread again. It should still remember the conversation.

## Logs

```bash
journalctl --user -u agent -f                    # what the bot is doing
tail -n 5 ~/agent/logs/usage.jsonl               # one JSON line per message: model, tokens, tools used, cost
```

`cost_usd_equiv` in the usage log is what the message would have cost on the API. On a subscription you don't pay it, but it's a decent measure of how much of your plan's usage a message eats.

## Day to day

```bash
systemctl --user restart agent      # after changing code or .env (SOUL.md and notes need no restart)
systemctl --user status agent
journalctl --user -u agent -n 50
```

Next: [how it works](05-how-it-works.md).
