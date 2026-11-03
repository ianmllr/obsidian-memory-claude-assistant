# 2. The Discord bot

I went with Discord as the interface because it's free, it's on every phone and computer, and threads, buttons and DMs come built in. Here you make the bot and a small private server for it.

## A server for you and the bot

In Discord, hit **+** (Add a Server), then Create My Own, then For me and my friends. Call it whatever you like. It's only going to be you and the bot in there.

Make two text channels:

- `chat` for actual conversations. Each message you post starts a thread, and the bot remembers what was said in that thread.
- `quick` for dumping notes, ideas, tasks and reminders. It files them and answers with a single line.

## The bot itself

Go to <https://discord.com/developers/applications> and click New Application. The name you give it is the name the bot shows up with.

Under **Bot** in the sidebar:

1. Click Reset Token and copy the token. You'll paste it into `.env` in chapter 4. Keep it to yourself, whoever has it can control your bot.
2. Turn on **Message Content Intent** under Privileged Gateway Intents. If you forget this, the bot connects but can't read any messages, and it crashes on start with `PrivilegedIntentsRequired`.
3. Switch off Public Bot so nobody else can add it to their server.

Then under **OAuth2 → URL Generator**, tick the `bot` scope and these permissions: View Channels, Send Messages, Create Public Threads, Send Messages in Threads, Read Message History. Open the URL it generates and add the bot to your server.

## Let it DM you

The heartbeat sends you DMs. Right-click the server icon, open Privacy Settings and turn on Direct Messages.

If you skip this, Discord refuses the DMs, and the error it gives is confusing: "Cannot send messages to this user due to having no mutual guilds" (code 50278), even though you're obviously in the same server. When that happens the bot posts in `#chat` with a mention instead, so nothing gets lost, but DMs are nicer.

## Your user ID

The bot only talks to you and ignores everyone else, which it does by user ID. Turn on Developer Mode under Settings → Advanced, then right-click your own name and pick Copy User ID. It's a long number like `123456789012345678`.

## Before moving on

- [ ] there's a server with `#chat` and `#quick`
- [ ] the bot is in it, with Message Content Intent turned on
- [ ] you've got the bot token and your user ID somewhere safe
- [ ] DMs are allowed on the server

Next: [the vault](03-vault.md).
