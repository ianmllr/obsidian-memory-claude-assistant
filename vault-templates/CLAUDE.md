# Rules for any AI working in this vault

This vault is my notes. These rules apply to every assistant that works here: the Discord assistant, and any other AI tool you point at the vault (Claude Code, an Obsidian AI plugin, ...).

## Folders

| Folder | What goes there |
|---|---|
| `Me/` | Facts about me: `about-me.md`, `Devices.md` |
| `Projects/` | One note per project |
| `Ideas/` | Ideas to come back to |
| `Home/` | Everyday life: meals, shopping, the house |
| `Misc/` | Anything that doesn't fit elsewhere |
| `Inbox/` | New notes waiting to be sorted |
| `Agent/` | The Discord assistant's files: `SOUL.md`, `MEMORY.md`, daily notes in `Agent/daily/` |
| `Private/` | Off-limits (see Privacy) |

`Vault index.md` links every note by folder. The Discord assistant regenerates it automatically, so never edit it by hand. A new top-level folder also needs a line in this table.

## Writing

- Only write to `Inbox/`, `Agent/` and the daily notes in `Agent/daily/`.
- New notes may be created in any folder in the table except `Private/` and `Agent/`. Never overwrite an existing note, and give the new note frontmatter tags (see Tags).
- Append. Never rewrite, reorder or delete existing text.
- Never edit, move or delete any other note unless I have approved that exact change.
- Every new entry or note links to at least one existing note with a `[[wikilink]]` when a related note exists. Don't invent links to notes that don't exist.
- Never edit files with `.sync-conflict-` in the name. Tell me they exist instead.

## Privacy

- Never read, search or quote anything in `Private/`.

## Tags

- Tags are lowercase, with hyphens instead of spaces: `#side-project`, not `#Side Project`.
- Reuse an existing tag before making a new one. Singular: `#todo` and `#idea`, never `#todos`, `#task` or `#ideas`.
- Every note has frontmatter tags: its folder's area plus one type, e.g. `tags: [home, food]` or `tags: [projects, web]`.
- Core tags for entries and tasks:
  - `#todo` for something I have to do
  - `#idea` for an idea to come back to
  - `#question` for something I want to find out
- Topic tags name a project or area, such as `#job-search`. Use one or two per entry, not five.

## Tasks

- A task is one line: `- [ ] what to do #todo`, plus any topic tag and links. A due date goes in as `📅 2026-11-30`.
- Write tasks in the note they belong to. For the Discord assistant, that's today's daily note.
- `Tasks.md` lists every open task in the vault. The Discord assistant regenerates it automatically, so never edit it by hand: tick tasks off in the note they live in.

## Style

- Keep notes short.
- Write in the language I used.
