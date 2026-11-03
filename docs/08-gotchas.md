# 8. Things that went wrong

All of these happened to me while building it. The fixes are already in the code, so this is mostly here so you know why things are the way they are, and what to look for if something similar happens to you.

## Tokens and cost

**Every message cost about 30 times more than it should.** A simple question that used one tool was burning around 20,000 tokens per step, while the system prompt was only about 2,000. It took some digging. Claude Code runs under your claude.ai account and automatically loads that account's connectors (Gmail, Google Drive, Docs and so on) into every session, and after the first tool call it lists all of them to the model. That's tens of thousands of tokens, resent on every step, for tools the bot isn't even allowed to use. Setting `strict_mcp_config=True` in `ClaudeAgentOptions` loads only the MCP servers you pass in yourself. My test question went from $0.0087 to $0.0003 in API terms. It's set in both `brain.py` and `heartbeat.py`; leave it there.

The way I found it, which works for other problems like it too: Claude Code keeps a transcript of every session in `~/.claude/projects/<folder>/<session>.jsonl`. List the entries by type and size, and the huge `attachment` entries stand out right away.

**The built-in tools add around 10,000 tokens.** If you don't pass `tools=[]`, Claude Code describes its own tools (Bash, Edit and the rest) to the model on every request. The bot passes an empty list and gives Claude only the vault tools.

**Old threads stay expensive.** A thread's transcript keeps everything that was ever sent in it. If a thread got bloated at some point, every reply in it reads that bloat again. Just start a new one.

**`ANTHROPIC_API_KEY` switches you to paid API usage.** With that variable set, Claude Code uses the key and API credits instead of your subscription. `main.py` refuses to start when it's set.

## The Agent SDK and the model

**Old threads didn't see today's note.** When a session is resumed, the SDK by default keeps the system prompt from that session's first message. Passing it as `{"type": "custom", "prompt": ..., "snapshot": False}` fixes that. You need a fairly recent Claude Code CLI for it; `claude update` if in doubt.

**Haiku puts things in the wrong place.** It would write `- [ ]` or `#todo` into the task text itself, or put the `📅` date in the text and also pass it as `due`, so you'd get `- [ ] - [ ] task` or two dates on one line. `capture` now strips the list markers, moves tags and dates out of the text into the right fields, and merges near-duplicate tags. Assume the model will do this sort of thing and clean it up in code.

**It used the wrong tool.** Even with "use `remember` for lasting facts, `propose_edit` for existing notes" in the instructions, Haiku saved a laptop's specs to `MEMORY.md` instead of suggesting a change to `Devices.md`. What fixed it in my tests was saying the same thing in both the tool description and `SOUL.md`, with concrete examples ("machines in `Me/Devices.md`"). If something has to hold no matter what, put it in code. Preferences are fine in the prompt, as long as they're concrete.

## Discord

`PrivilegedIntentsRequired` on start means Message Content Intent is off in the developer portal.

"Cannot send messages to this user due to having no mutual guilds" (50278) shows up even when you share a server. It means DMs from that server are blocked; turn on Direct Messages in the server's privacy settings. Until then the bot falls back to a thread in `#chat`.

If every message gets answered twice, two copies of the bot are running: on two machines, or a test run next to the service. `pgrep -af main.py` shows them.

Discord cuts messages off at 2,000 characters, which is why `send_long()` splits long replies and proposed diffs get shortened.

## Syncthing and Obsidian

The Syncthing service kept failing with "Failed to acquire lock: is another Syncthing instance already running?" because I'd also started Syncthing from the desktop menu. Use only the service.

The `.sync-conflict-` files that kept turning up were almost all `.obsidian/workspace.json`, Obsidian's window layout, which it rewrites whenever you switch tabs. Ignoring it in `.stignore` on every device (chapter 1) made them stop. Conflicts in actual notes are worth looking at by hand. The assistant never touches them, but the heartbeat tells you when new ones appear.

Syncthing's versioning doesn't cover the assistant's own edits, since it only keeps files that were replaced by changes from other devices. That's what the hourly snapshot in chapter 7 is for.

## Linux and hardware

**"Running on battery" DMs several times a day.** On my ThinkPad, the USB-C charger shows as offline for 5 to 10 seconds at a time while the battery sits at its charge limit. Whenever a health check happened to land in one of those moments, it decided the power was out, and a bit later that it was back. Now it only reports a power cut if the charger reads offline in every sample over about 20 seconds.

**Nothing from `print()` in the service log.** Python buffers its output when it isn't writing to a terminal. The service sets `PYTHONUNBUFFERED=1`.

**`claude` not found when running as a service.** systemd user services start with a bare-bones `PATH`. `install.sh` adds the folder `claude` lives in to the front of it.

Next: [making it yours](09-customise.md).
