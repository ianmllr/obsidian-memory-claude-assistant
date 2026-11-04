# 3. The vault

The vault is the assistant's memory, and it's nothing more than a folder of Markdown files. This chapter sets up the layout it expects and the few files that tell it who you are and how to behave.

## Layout

You can use whatever folders you want. The templates start from this:

```
Your vault/
├── CLAUDE.md          rules for every AI that works in the vault
├── Vault index.md     generated: every note, by folder
├── Tasks.md           generated: every open task, by date and by note
├── Me/                about-me.md, Devices.md
├── Projects/          one note per project
├── Ideas/
├── Home/
├── Misc/
├── Inbox/             new notes waiting to be sorted
├── Agent/             the assistant's own files
│   ├── SOUL.md          its personality and instructions
│   ├── MEMORY.md        facts it has learned about you
│   └── daily/           one note per day: captures and tasks
└── Private/           invisible to the assistant, enforced in code
```

Copy the templates in and make the empty folders:

```bash
VAULT=~/Documents/ObsidianVault          # your vault
cp -rn vault-templates/. "$VAULT"/       # -n: never overwrite a file you already have
mkdir -p "$VAULT"/{Projects,Ideas,Home,Misc,Inbox,Private,Agent/daily}
```

If you already have a pile of notes, you can leave them where they are or sort them into folders. Obsidian links go by note name (`[[My note]]`), not by path, so moving things around doesn't break anything. I had 45 loose notes and had Claude Code suggest a folder for each one; it took a few minutes. If you end up with different folder names than mine, update the table in `CLAUDE.md` and `FOLDER_INFO` near the top of `assistant/tools.py`.

## The files that matter

**`CLAUDE.md`** is the house rules for any AI working in the vault: which folders it may write to, where it may create new notes, that it only ever appends to existing ones, that it needs your OK before editing a note, and how tags and tasks look. The assistant reads it with every message, and so does Claude Code if you ever point it at the vault. The important rules are also hard-coded in `tools.py`, so they hold even if the model gets creative.

**`Agent/SOUL.md`** is the assistant's personality and job description: how to talk, which tool to use when, how to learn about you. Put your name in place of `<your name>` on the first line. The rest you can change whenever you like. It's read fresh with every message, so changes show up immediately, also in threads that are already going.

**`Me/about-me.md` and `Me/Devices.md`** are pinned. Any note that starts with

```yaml
---
agent: pin
---
```

goes along with every single message. Pin the handful of things it should always know, like who you are, your machines, maybe what you're working towards, and not much more, because every pinned note costs tokens on every message. Everything else it finds by searching when it needs it. Write a few true lines in `about-me.md` to start with. It doesn't have to be complete, the assistant will suggest additions as it gets to know you.

**`Agent/MEMORY.md`** starts out empty. When you tell it something lasting that doesn't fit an existing note ("my sister's birthday is 14 March"), it adds a line here, and since the file is sent with every message, it knows from then on.

**`Private/`** is off limits. Search, read and every other tool refuse anything in there. It's still a normal folder though, and Syncthing copies it unencrypted to all your devices, so keep actual passwords in a password manager.

## Tags

Every note gets frontmatter tags: the area it belongs to plus a type, like `tags: [home, food]`. Entries and tasks get inline tags, usually `#todo`, `#idea` or `#question`, plus one or two topic tags such as `#job-search`.

Keep them singular and lowercase. `#idea`, not `#ideas`. The code merges the usual near-duplicates by itself (`ideas` becomes `idea`, `todos` and `task` become `todo`), because the model will happily invent them otherwise. Tags written as `` `code` ``, like the examples in the rules file, don't count.

## Tasks

A task is a single line anywhere in the vault:

```markdown
- [ ] Renew the domain 📅 2026-11-06 #todo #web [[Portfolio site]]
```

The date is optional. If it's there, the heartbeat reminds you that morning. `Tasks.md` is rebuilt by the assistant every few minutes, with dated tasks at the top and then everything grouped by note. You tick things off in the note they're in, which is one click away from the list. No Obsidian plugin needed.

## Before moving on

- [ ] templates copied, your name in `Agent/SOUL.md`
- [ ] a few lines in `Me/about-me.md` and `Me/Devices.md`
- [ ] the folders exist, including `Agent/daily/` and `Private/`

Next: [installing it](04-install.md).
