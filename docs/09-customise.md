# 9. Making it yours

## Personality

Edit `Agent/SOUL.md` in Obsidian. It's read again with every message, so you don't need to restart anything, and existing threads pick up the change too. That's where the tone goes, the language, what it should save and what it should leave alone.

## Models

In `assistant/brain.py`:

```python
MODELS = {"haiku": "claude-haiku-5-5", "sonnet": "claude-sonnet-5-5", "opus": "claude-opus-5-5"}
DEFAULT_MODEL = "haiku"
MAX_TURNS = 10
```

Change the IDs when new models come out. `ESCALATE_TO=sonnet,opus` in `.env` lets Haiku hand things to Opus as well, and `/sonnet` or `/opus` at the start of a message always works.

## Folders and the index

Rename and add folders as you like. Update the table in `CLAUDE.md`, and `FOLDER_INFO` / `FOLDER_ORDER` in `tools.py` so `Vault index.md` gets the right descriptions; folders you don't list still show up, just without a description. If you want things to land in particular places, say so in the "Learning about the user" part of `SOUL.md`, e.g. "recipes go in `Home/`". `NO_NEW_NOTES` in `tools.py` lists the top-level folders `create_note` may not add notes to; add any folder that has its own structure you don't want the assistant to mess with.

The channel names are `CHAT_CHANNEL` and `QUICK_CHANNEL` in `.env`.

## Adding a tool

All tools live in `make_vault_server()` in `tools.py`. A new one looks like this:

```python
@tool(
    "word_count",                                         # the name the model sees
    "Count the words in one note, by path or [[name]].",  # when and how to use it
    {"path": str},                                        # arguments
)
async def word_count(args):
    try:
        path, rel = find_note(vault, args["path"])        # enforces the vault rules
    except VaultError as e:
        return _err(str(e))
    n = len(path.read_text(encoding="utf-8").split())
    return _ok(f"{rel}: {n} words")
```

Add it to the `tools = [...]` list at the bottom of `make_vault_server()`, add `"word_count"` to `TOOL_NAMES` at the top (that's what actually allows the model to call it), mention it in `SOUL.md`, and restart. A few habits that kept mine out of trouble: send every path through `find_note()` or `safe_path()`, never let a tool overwrite or delete text (`create_note` opens files with mode `"x"` for that reason), and record writes in `actions` so `main.py` can show you exactly what changed.

## Using a locally run LLM

Only one layer of this talks to the model, so you can point it at a model on your own hardware, for example with [Ollama](https://ollama.com) or [LM Studio](https://lmstudio.ai), which both offer an OpenAI-compatible API, and keep everything else.

Nothing changes in the Discord side (`main.py`), the vault rules or the tools' actual work: `search_notes()`, `read_note()`, `capture_entry()`, `create_note_file()`, `append_memory()`, `check_edit()` and `apply_edit()` in `tools.py` are ordinary Python functions. The heartbeat's scheduling and health checks, the templates, the snapshots and the services stay as they are.

What you'd replace:

- `ask()` in `brain.py`. Instead of the Agent SDK, write a small loop: send the system prompt, the conversation so far and the tool definitions to the local model's `/v1/chat/completions` endpoint; when it asks for a tool, call the matching function from `tools.py` and send the result back; repeat until it answers or you hit `MAX_TURNS`. Keep filling in `actions` the same way and the "📥 Saved…" lines and Approve/Reject buttons keep working.
- Sessions. The SDK stores each thread's history for you. With a local model you keep the message history per thread yourself, e.g. as JSON next to `state/sessions.json`, and send it along every time.
- `Heartbeat.think()` in `heartbeat.py`. That's a single request without tools, the easy part.
- The names in `MODELS`, and maybe escalation. A nice combination is a local model by default that escalates to Claude for the hard questions.

Some things to know first. Tool use is where small models struggle most, so pick one that's good at function calling and expect to tighten the tool descriptions. The code-side rules matter even more with a weaker model, so keep them. A 7–8B model wants roughly 8 GB of free RAM or VRAM and is slow on an old laptop's CPU; with a GPU or Apple Silicon it's pleasant, and the bot can also call a model running on another machine on your network. Images only work if the local model can see. On the plus side, with everything local, your notes and mail never leave your network.

## Ideas

Some things I'd like to add at some point:

- reminders at a time of day, by storing `⏰ 15:00` next to the date and checking it in `Heartbeat.tick()`
- ticking tasks off from Discord, with a `complete_task` tool that proposes the `- [ ]` → `- [x]` change through the normal approval flow
- web search. The SDK can do it, but web pages bring the same prompt-injection problem as email, so think it through first
- a dead man's switch. The heartbeat can't tell you the computer is off, but a free service like healthchecks.io can email you when the bot stops checking in
- voice notes: transcribe audio attachments and `capture` them
